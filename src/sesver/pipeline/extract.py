"""COZ - serbest metinden yapilandirilmis yardim cagrisi cikarir.

Projenin en zor NLP problemi burasi. Cagrilar panik halinde, cogu zaman
Turkce klavye olmadan, yarim cumlelerle yazilir:

    "antakya armutlu mah 5. sok yilmaz apt 3. kat 4 kisiyiz sesler geliyor"
    "Defne'de anneannem var haber alamiyoruz lutfen"
    "ADIYAMAN SITELER MAH. BINA COKTU 2 COCUK ICERIDE"

Cikarilan alanlar: il / ilce / mahalle / sokak / bina / kat / kisi sayisi /
kirilganlik / canlilik isareti.

Kural tabanli hat burada bilerek sade tutulmustur: gorevi, egitilmis
DIVAN-COZ modeline karsi durust bir taban cizgisi olusturmaktir. Model
kazancini bu taban cizgisine gore raporluyoruz.
"""

from __future__ import annotations

import re

from ..config import CANLILIK_SOZCUKLER, KIRILGAN_SOZCUKLER
from ..data.gazetteer import Gazetteer, varsayilan_gazetteer
from ..metin import icerir, normalize, sayi_bul, yakin_esles
from ..schemas import Cagri, Konum, Cozunurluk, Mesaj

# "5. sokak", "5.sok", "5 nolu sokak"
_SOKAK = re.compile(r"(\d+)\s*\.?\s*(?:nolu\s+)?(?:sokak|sok|cadde|cad)\b")
# "yilmaz apartmani", "gunes apt", "cinar sitesi"
_BINA = re.compile(r"([a-z0-9]+)\s+(?:apartmani|apartman|apt|sitesi|site|blok|bina)\b")
# "3. kat", "3.katta", "zemin kat"
_KAT = re.compile(r"(\d+)\s*\.?\s*kat")
_ZEMIN = re.compile(r"\b(zemin|bodrum)\s*kat")

_KISI_KALIP = ("kisiyiz", "kisi", "kisilik", "kisiyle", "canimiz")

# Mahalle adayini yakalar: "armutlu mah", "siteler mahallesi"
_MAHALLE = re.compile(r"([a-z0-9]+)\s+(?:mahallesi|mahalle|mah)\b")


# Adres yapisi sozcukleri bina/mahalle ADI olarak yakalanmamalidir.
# "siteler mah bina coktu" ifadesinde bina adi "mah" degildir.
_YAPI_SOZCUKLERI = frozenset(
    {
        "mah", "mahalle", "mahallesi", "sok", "sokak", "cad", "cadde",
        "caddesi", "no", "numara", "bina", "apt", "apartman", "apartmani",
        "site", "sitesi", "blok", "kat", "acil", "yardim", "enkaz",
    }
)


class Cozumleyici:
    """Mesajdan Cagri uretir. Model hatti ayni arayuzu uygular."""

    def __init__(self, gazetteer: Gazetteer | None = None) -> None:
        self.g = gazetteer or varsayilan_gazetteer()

    def __call__(self, mesaj: Mesaj) -> Cagri:
        n = normalize(mesaj.metin)
        konum = self._konum(n, mesaj)
        return Cagri(
            mesaj=mesaj,
            konum=konum,
            kisi_sayisi=sayi_bul(mesaj.metin, _KISI_KALIP),
            kirilgan=icerir(mesaj.metin, KIRILGAN_SOZCUKLER),
            ses_var=icerir(mesaj.metin, CANLILIK_SOZCUKLER),
            aciklama=mesaj.metin[:280],
        )

    # --- ic yardimcilar ---

    def _konum(self, n: str, mesaj: Mesaj) -> Konum:
        k = Konum()

        # 1) Mahalle en bilgilendirici alan: bulunursa il ve ilce de gelir.
        mah_aday = None
        m = _MAHALLE.search(n)
        if m and m.group(1) not in _YAPI_SOZCUKLERI:
            mah_aday = m.group(1)
        else:
            # Mahalle sozcugu yazilmamis olabilir; sozlukteki adlari tara.
            for token in n.split():
                if len(token) > 4 and self.g.mahalle_ara(token):
                    mah_aday = token
                    break

        if mah_aday:
            vurus = self.g.mahalle_ara(mah_aday)
            if vurus:
                k.il, k.ilce, k.mahalle, k.lat, k.lon = vurus
                k.cozunurluk = Cozunurluk.MAHALLE
                k.guven = 0.62

        # 2) Ilce adi acikca gecmis olabilir; mahalle yoksa ilceye duseriz.
        if not k.mahalle:
            for token in n.split():
                if len(token) < 4:
                    continue
                vurus = self.g.ilce_merkez(token)
                if vurus:
                    k.il, k.ilce, k.lat, k.lon = vurus
                    k.cozunurluk = Cozunurluk.ILCE
                    k.guven = 0.34
                    break

        # 3) Il adi son care.
        if k.cozunurluk is Cozunurluk.YOK:
            il = yakin_esles(" ".join(n.split()[:6]), self.g.iller, esik=0.9)
            for token in n.split():
                il = il or yakin_esles(token, self.g.iller, esik=0.88)
            if il:
                k.il = il
                k.cozunurluk = Cozunurluk.IL
                k.guven = 0.15

        # 4) Sokak ve bina cozunurlugu keskinlestirir.
        s = _SOKAK.search(n)
        if s:
            k.sokak = f"{s.group(1)}. Sokak"
            if k.cozunurluk is Cozunurluk.MAHALLE:
                k.cozunurluk = Cozunurluk.SOKAK
                k.guven = 0.74

        b = _BINA.search(n)
        if b and b.group(1) not in _YAPI_SOZCUKLERI:
            k.bina = b.group(1).title()
            if k.cozunurluk in (Cozunurluk.SOKAK, Cozunurluk.MAHALLE):
                k.cozunurluk = Cozunurluk.BINA
                k.guven = 0.86

        kat = _KAT.search(n)
        if kat:
            try:
                k.kat = int(kat.group(1))
            except ValueError:
                pass
        elif _ZEMIN.search(n):
            k.kat = 0

        # 5) Cihaz konum etiketi varsa en guvenilir sinyaldir:
        #    yapilandirilmis besteciden gelen cagri burada one gecer.
        if mesaj.konum_etiketi:
            k.lat, k.lon = mesaj.konum_etiketi
            k.cozunurluk = Cozunurluk.BINA
            k.guven = max(k.guven, 0.92)

        return k

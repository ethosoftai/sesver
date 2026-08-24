"""BIRLESTIR - ayni olaya isaret eden cagrilari tek goreve indirger.

Hacim problemi burada cozulur. Tek bir ailenin cagrisi on binlerce kez
paylasilir; her paylasim yeni bir ihbar gibi gorunur ve ekipler ayni binaya
defalarca yonlendirilir.

Kumeleme uc sinyalin birlikteligiyle yapilir:
  1. mekan yakinligi (haversine, metre)
  2. metin benzerligi (normalize edilmis)
  3. zaman penceresi

Onemli ayrim: ``bagimsiz_kaynak`` sayisi kopya sayisindan farklidir. Ayni
hesabin 50 tekrari guveni artirmaz; iki farkli hesabin ayni binayi bildirmesi
UCGENLEMEDIR ve guveni ciddi bicimde artirir.

KONUMSUZ CAGRILAR
-----------------
Triyaj bilerek yuksek anma icin ayarlidir, dolayisiyla adres icermeyen bazi
mesajlar da CAGRI olarak gelir. Bunlar gorev kuyruguna SOKULMAZ: konumu
olmayan bir kayit sahaya gonderilemez, kuyrukta yalnizca gurultu yapar.
Ayri bir havuzda toplanip gonullu panelinde adres zenginlestirmesine dusurler.
Kayit yine SILINMEZ - yalnizca dogru kuyruga gider.
"""

from __future__ import annotations

import math
from itertools import count

from ..config import ESIK
from ..metin import benzerlik
from ..schemas import Cagri, Cozunurluk, Gorev

DUNYA_YARICAP_M = 6_371_000.0

KESKINLIK = {
    Cozunurluk.BINA: 5,
    Cozunurluk.SOKAK: 4,
    Cozunurluk.MAHALLE: 3,
    Cozunurluk.ILCE: 2,
    Cozunurluk.IL: 1,
    Cozunurluk.YOK: 0,
}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Iki koordinat arasi mesafe, metre."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * DUNYA_YARICAP_M * math.asin(math.sqrt(a))


class Birlestirici:
    """Artimli kumeleme: akis halinde gelen cagrilari acik gorevlere baglar.

    Performans notu: naif uygulama her cagriyi TUM gorevlerle karsilastirir ve
    O(n*m) buyur. Gorevler mahalle anahtarina gore kovalanir; boylece
    karsilastirma yalnizca ayni mahalledeki gorevlerle yapilir.
    """

    def __init__(self) -> None:
        self._sayac = count(1)
        self.gorevler: dict[str, Gorev] = {}
        self.konumsuz: list[Cagri] = []
        self._kova: dict[str, list[str]] = {}

    # --- akis girisi ---

    def ekle(self, cagri: Cagri) -> Gorev | None:
        """Cagriyi bir goreve baglar.

        Konumu cozulemeyen cagri icin None doner ve kayit ``konumsuz``
        havuzuna alinir.
        """
        if cagri.konum.bos_mu():
            self.konumsuz.append(cagri)
            return None

        hedef = self._en_iyi_eslesme(cagri)
        if hedef is None:
            hedef = Gorev(
                id=f"G-{next(self._sayac):06d}",
                konum=cagri.konum,
                olusma_ts=cagri.mesaj.ts,
                son_teyit_ts=cagri.mesaj.ts,
            )
            hedef.iz.append("yeni gorev acildi")
            self.gorevler[hedef.id] = hedef
            self._kova.setdefault(self._kova_anahtari(cagri.konum), []).append(hedef.id)
        else:
            if KESKINLIK[cagri.konum.cozunurluk] > KESKINLIK[hedef.konum.cozunurluk]:
                eski = self._kova_anahtari(hedef.konum)
                hedef.konum = cagri.konum
                yeni = self._kova_anahtari(hedef.konum)
                if eski != yeni:
                    self._kova.get(eski, []).remove(hedef.id)
                    self._kova.setdefault(yeni, []).append(hedef.id)
                hedef.iz.append("konum keskinlestirildi")
            hedef.son_teyit_ts = max(hedef.son_teyit_ts, cagri.mesaj.ts)

        hedef.cagrilar.append(cagri)
        return hedef

    # --- ic yardimcilar ---

    @staticmethod
    def _kova_anahtari(konum) -> str:
        """Mahalle duzeyinde kaba kova. Adaylari bu kova icinde ararız."""
        return f"{konum.il or ''}|{konum.ilce or ''}|{konum.mahalle or ''}".lower()

    def _adaylar(self, cagri: Cagri):
        for gid in self._kova.get(self._kova_anahtari(cagri.konum), ()):
            yield self.gorevler[gid]

    def _en_iyi_eslesme(self, cagri: Cagri) -> Gorev | None:
        en_iyi: tuple[float, Gorev] | None = None
        for gorev in self._adaylar(cagri):
            skor = self._skor(cagri, gorev)
            if skor is None:
                continue
            if en_iyi is None or skor > en_iyi[0]:
                en_iyi = (skor, gorev)
        return en_iyi[1] if en_iyi else None

    @staticmethod
    def _uyumlu(a, b) -> bool:
        """Iki adres ayni yeri gosterebilir mi?

        Kritik kural: METIN BENZERLIGI ADRES CAKISMASININ YERINE GECMEZ.

        Afet cagrilarinin cogu ayni kaliptan cikar ("... mah ... sokak ...
        apartmani ... kat enkaz altindayiz"). Iki farkli binanin metinleri
        %80 benzer olabilir. Yalnizca metne bakan bir kumeleyici, komsu iki
        enkazi tek goreve indirger ve ikinci binaya kimse gitmez.

        Bu yuzden alanlar tek tek karsilastirilir: iki tarafta da DOLU olan
        bir alan celisiyorsa adresler farklidir, benzerlik ne olursa olsun.
        Bir taraf bos ise (daha az keskin cagri) adresler uyumlu sayilir ve
        birlesme serbesttir - bu, kaba cagrinin keskin olana baglanmasini
        saglar.
        """
        for alan in ("il", "ilce", "mahalle", "sokak", "bina"):
            x, y = getattr(a, alan), getattr(b, alan)
            if x is not None and y is not None and x != y:
                return False
        return True

    def _skor(self, cagri: Cagri, gorev: Gorev) -> float | None:
        """Eslesme skoru; esikleri gecmezse None."""
        if abs(cagri.mesaj.ts - gorev.son_teyit_ts) / 60.0 > ESIK.zaman_penceresi_dk:
            return None

        a, b = cagri.konum, gorev.konum
        if not self._uyumlu(a, b):
            return None

        mesafe = None
        if None not in (a.lat, a.lon, b.lat, b.lon):
            mesafe = haversine_m(a.lat, a.lon, b.lat, b.lon)
            if mesafe > ESIK.mekan_yaricap_m:
                return None

        anahtar_ayni = a.anahtar() == b.anahtar()
        ilk = gorev.cagrilar[0].aciklama if gorev.cagrilar else ""
        metin = 1.0 if anahtar_ayni else benzerlik(cagri.aciklama, ilk)

        # Adresi zayif olan taraflarda (bina yok) metin benzerligi hala
        # gereklidir; aksi halde ayni mahallenin tum kaba cagrilari birlesir.
        # Adres anahtarlari birebir tutmuyorsa metin benzerligi ZORUNLUDUR.
        #
        # Onceki surumde bu kosul yalnizca iki taraf da bina duzeyinde
        # degilse araniyordu. Yazim bozulmasi eklenince su hata ortaya cikti:
        # bir kayitta bina adi bozulup cikarilamayinca alan None kalir,
        # ``_uyumlu`` "bir taraf bos" diye gecirir ve KOMSU BIR BINAYLA
        # birlesir. Olculen kume safligi 0,99'dan 0,78'e dustu.
        #
        # Eksik alan, celismeyen alan degildir: yalnizca bilinmeyen alandir.
        # Bu yuzden anahtar tam tutmadigi her durumda metin de benzemelidir.
        if not anahtar_ayni and metin < ESIK.metin_benzerlik:
            return None

        yakinlik = 1.0 if mesafe is None else max(0.0, 1.0 - mesafe / ESIK.mekan_yaricap_m)
        return 2.0 * float(anahtar_ayni) + metin + yakinlik

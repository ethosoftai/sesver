"""DOGRULA - her goreve kalibre bir guven skoru verir.

Temel tasarim ilkesi: KAYIT SILINMEZ, SIRALANIR.

Kurtarma baglaminda maliyet asimetriktir. Gercek cagriyi elemek bir aileyi
oldurur; sahte cagriyi gecirmek kit kurtarma kapasitesini bosa harcar ve o
kapasite baska yerde birini oldurur. Ikisi de olumculdur, bu yuzden ikili
"dogru/yanlis" siniflandirmasi yanlis tasarimdir. Her kayit bir skor alir ve
oncelik kuyruguna girer; hicbir sey yok edilmez, yalnizca asagi iner.

Guven dort sinyalden toplanir:
  1. UCGENLEME    - bagimsiz kaynak sayisi (Standby Task Force protokolunun
                    otomatiklestirilmis hali)
  2. DURUS        - yanit zincirindeki teyit / yalanlama (RumourEval hatti)
  3. HESAP        - yas, bolgede gecmis, onceki isabet
  4. ADRES        - konum cozunurlugu ve sozluk dogrulamasi
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..config import CELISKI_SOZCUKLER, ESIK, KAPATMA_SOZCUKLER
from ..metin import icerir
from ..schemas import Cozunurluk, Durum, Gorev, Mesaj


class Durus(str, Enum):
    """Bir yanitin kaynak iddiaya karsi tutumu."""

    TEYIT = "teyit"
    YALANLAMA = "yalanlama"
    COZULDU = "cozuldu"       # "kurtarildilar" - iddia dogruydu, artik gecersiz
    SORGU = "sorgu"
    ILGISIZ = "ilgisiz"


TEYIT_SOZCUKLER = (
    "teyit ettim", "ben de gordum", "ben de gördüm",
    "komsusuyum", "komşusuyum", "ayni binada", "aynı binada", "oradayim",
    "oradayım", "ekip geldi", "hala bekliyorlar", "hâlâ bekliyorlar",
)

SORGU_SOZCUKLER = ("teyit eden", "dogru mu", "doğru mu", "kim biliyor", "guncel mi", "güncel mi")


def durus_belirle(yanit: Mesaj) -> Durus:
    """Kural tabanli duruş sinifi.

    Egitilmis Turkce durus modeli bu fonksiyonun yerine gecer; arayuz aynidir.
    Sirasi onemli: cozuldu > yalanlama > sorgu > teyit.
    "dogru mu" bir sorudur, teyit degildir; sorgu once denenir.
    """
    if icerir(yanit.metin, KAPATMA_SOZCUKLER):
        return Durus.COZULDU
    if icerir(yanit.metin, CELISKI_SOZCUKLER):
        return Durus.YALANLAMA
    if icerir(yanit.metin, SORGU_SOZCUKLER):
        return Durus.SORGU
    if icerir(yanit.metin, TEYIT_SOZCUKLER):
        return Durus.TEYIT
    return Durus.ILGISIZ


@dataclass(slots=True)
class GuvenDokumu:
    """Skorun nereden geldigi. Aciklanabilirlik icin goreve iliştirilir."""

    ucgenleme: float = 0.0
    durus: float = 0.0
    hesap: float = 0.0
    adres: float = 0.0

    @property
    def toplam(self) -> float:
        ham = 0.5 + self.ucgenleme + self.durus + self.hesap + self.adres
        return round(min(max(ham, 0.0), 1.0), 3)

    def acikla(self) -> str:
        return (
            f"ucgenleme={self.ucgenleme:+.2f} durus={self.durus:+.2f} "
            f"hesap={self.hesap:+.2f} adres={self.adres:+.2f}"
        )


ADRES_KATKI = {
    Cozunurluk.BINA: 0.18,
    Cozunurluk.SOKAK: 0.12,
    Cozunurluk.MAHALLE: 0.04,
    Cozunurluk.ILCE: -0.04,
    Cozunurluk.IL: -0.12,
    Cozunurluk.YOK: -0.25,
}


class Dogrulayici:
    def __init__(self) -> None:
        self.yanitlar: dict[str, list[Mesaj]] = {}

    def yanit_ekle(self, yanit: Mesaj) -> None:
        """Yanit zincirini biriktirir; durus analizi bunun uzerinde calisir."""
        if yanit.yanit_verilen:
            self.yanitlar.setdefault(yanit.yanit_verilen, []).append(yanit)

    def __call__(self, gorev: Gorev) -> Gorev:
        d = GuvenDokumu()

        # 1) Ucgenleme: bagimsiz kaynak sayisi. Ayni hesabin tekrari saymaz.
        bagimsiz = gorev.bagimsiz_kaynak
        if bagimsiz >= ESIK.bagimsiz_kaynak_gerekli:
            d.ucgenleme = min(0.15 + 0.08 * (bagimsiz - 2), 0.33)
        elif bagimsiz == 1 and gorev.kopya_sayisi > 20:
            # Tek kaynak, cok kopya: yayilim var ama teyit yok.
            d.ucgenleme = -0.08

        # 2) Durus: yanit zincirinden gelen teyit / yalanlama / cozulme.
        teyit = yalanlama = cozuldu = 0
        for cagri in gorev.cagrilar:
            for yanit in self.yanitlar.get(cagri.mesaj.id, ()):
                s = durus_belirle(yanit)
                teyit += s is Durus.TEYIT
                yalanlama += s is Durus.YALANLAMA
                cozuldu += s is Durus.COZULDU
        d.durus = min(0.10 * teyit, 0.25) - min(0.18 * yalanlama, 0.45)
        gorev.celiski = yalanlama
        gorev.kapatma_sinyali += cozuldu

        # 3) Hesap: yeni hesap ve bolge gecmisi olmamasi supheyi artirir.
        yeni = sum(1 for c in gorev.cagrilar if c.mesaj.hesap.yeni_hesap)
        yerli = sum(1 for c in gorev.cagrilar if c.mesaj.hesap.bolgede_gecmis)
        if gorev.cagrilar:
            oran_yeni = yeni / len(gorev.cagrilar)
            oran_yerli = yerli / len(gorev.cagrilar)
            d.hesap = 0.10 * oran_yerli - 0.20 * oran_yeni

        # 4) Adres: konum ne kadar keskinse o kadar eyleme donusturulebilir.
        d.adres = ADRES_KATKI[gorev.konum.cozunurluk]

        gorev.guven = d.toplam
        gorev.iz.append(f"guven={gorev.guven} [{d.acikla()}]")

        # Durum atamasi. Hicbir dalda kayit silinmez.
        if gorev.kapatma_sinyali >= ESIK.kapatma_sinyali_gerekli:
            gorev.durum = Durum.KAPATILDI
        elif gorev.guven >= ESIK.guven_yuksek and bagimsiz >= ESIK.bagimsiz_kaynak_gerekli:
            gorev.durum = Durum.DOGRULANDI
        elif gorev.guven >= ESIK.guven_alt:
            gorev.durum = Durum.DOGRULANIYOR
        else:
            gorev.durum = Durum.YENI
        return gorev

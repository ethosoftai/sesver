"""ONCELIKLENDIR - kuyrugun sirasini belirler.

Kritik tasarim karari: ONCELIK, GUVENE ESIT DEGILDIR.

Onceligi dogrudan guven skoruna baglamak, dusuk guvenli ama yuksek riskli
cagrilari (tek kaynakli ama "3 cocuk var, sesler geliyor") kuyrugun dibine
gomerdi. Bunun yerine:

    oncelik = siddet * zaman_baskisi * sqrt(guven)

Karekok, guvenin etkisini yumusatir: guven bir SIRALAMA carpanidir, bir
ELEME kapisi degil. Guveni 0.36 olan bir cagri, guveni 0.81 olan bir cagriya
gore yalnizca yarim carpan kaybeder - kuyruktan dusmez.

Zaman baskisi "altin 72 saat" egrisini izler: ilk saatlerde hizla yukselir,
sonra yuksek platoda kalir. Enkaz altindaki bir insanin hayatta kalma
olasiligi zamanla duser; bu, gorevin degerinin dustugu anlamina gelmez,
aciliyetinin arttigi anlamina gelir.
"""

from __future__ import annotations

import math

from ..schemas import Cozunurluk, Durum, Gorev

# Konum ne kadar keskinse ekip o kadar hizli ulasir: eyleme donusturulebilirlik.
EYLEM_CARPANI = {
    Cozunurluk.BINA: 1.00,
    Cozunurluk.SOKAK: 0.92,
    Cozunurluk.MAHALLE: 0.70,
    Cozunurluk.ILCE: 0.40,
    Cozunurluk.IL: 0.20,
    Cozunurluk.YOK: 0.10,
}


def siddet(gorev: Gorev) -> float:
    """Olayin insani agirligi. 0-1 araligina sikistirilmis."""
    s = 0.35
    if any(c.ses_var for c in gorev.cagrilar):
        s += 0.30            # canlilik isareti en guclu tek sinyal
    if any(c.kirilgan for c in gorev.cagrilar):
        s += 0.18            # cocuk, yasli, hamile, engelli, kronik hasta
    kisi = max((c.kisi_sayisi or 0) for c in gorev.cagrilar) if gorev.cagrilar else 0
    if kisi:
        s += min(0.02 * kisi, 0.15)
    kat = gorev.konum.kat
    if kat is not None and kat <= 0:
        s += 0.05            # bodrum/zemin: ulasim ve hava boslugu farkli
    return min(s, 1.0)


def zaman_baskisi(gorev: Gorev, simdi: float) -> float:
    """Altin 72 saat egrisi: hizli yukselis, yuksek plato."""
    saat = max((simdi - gorev.olusma_ts) / 3600.0, 0.0)
    return round(min(0.55 + 0.45 * (1 - math.exp(-saat / 6.0)), 1.0), 4)


def oncelik_hesapla(gorev: Gorev, simdi: float) -> float:
    if gorev.durum in (Durum.KAPATILDI, Durum.ASILSIZ):
        return 0.0

    taban = siddet(gorev) * zaman_baskisi(gorev, simdi) * math.sqrt(max(gorev.guven, 0.01))
    taban *= EYLEM_CARPANI[gorev.konum.cozunurluk]

    # Celiski cezasi: yalanlayan yanitlar sirayi dusurur ama sifirlamaz.
    if gorev.celiski:
        taban *= max(0.35, 1.0 - 0.22 * gorev.celiski)

    # Bayat kayit gorunur kalir, en alta iner.
    if gorev.durum is Durum.BAYAT:
        taban *= 0.25

    return round(taban, 4)


class Onceliklendirici:
    def __call__(self, gorevler: list[Gorev], simdi: float) -> list[Gorev]:
        for g in gorevler:
            g.oncelik = oncelik_hesapla(g, simdi)
        return sorted(gorevler, key=lambda g: g.oncelik, reverse=True)

"""Yetkili veri kayit defteri: iddia turu -> cevabi kimde -> nasil sorulur.

B hattinin kalbi burasi ve tasarimin en onemli fikri sudur:

    SISTEM KAHIN DEGIL, YONLENDIRICIDIR.

"Baraj patladi" iddiasinin cevabi su anda bir veritabaninda duruyor. DSI'nin
o barajda telemetrisi var: su seviyesi, kapak durumu, son okuma saati. Sorun
bilgi eksikligi degil, YONLENDIRME GECIKMESIDIR. Soylenti dort dakikada iki
yuz bin kisiye ulasir, cevap uc saat sonra basin aciklamasiyla gelir.

Bu modul o gecikmeyi kapatir.

DURUSTLUK NOTU
--------------
Asagidaki veri kaynaklari SIMULASYONDUR. Gercek kurum entegrasyonu (DSI,
TEIAS, BOTAS, Borsa Istanbul) protokol ve yetkilendirme gerektirir; yarisma
prototipinde gerceklenmemistir. Arayuz gercek entegrasyona birebir uyacak
sekilde tasarlanmistir: ``VeriKaynagi`` uygulamasini degistirmek yeterlidir.
Bu durum teknik raporda ve sunumda acikca belirtilir.

Ayni not ``Kayit.mail`` alanlari icin de gecerlidir: asagidaki adresler
ornektir, gercek kurum kutusu degildir. Uretimde bu alan gercek kurumsal
adresle degistirilir.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import IddiaTuru


@dataclass(frozen=True, slots=True)
class Yanit:
    """Yetkili kaynaktan donen cevap."""

    dogrulandi: bool          # iddia dogru mu
    ozet: str
    kaynak: str
    okuma_ts: float
    otomatik: bool = True     # makine mi cevapladi, insan mi

    @property
    def damga(self) -> str:
        an = time.strftime("%H:%M", time.localtime(self.okuma_ts))
        kip = "otomatik telemetri" if self.otomatik else "kurum beyani"
        return f"{self.kaynak} - {kip} - {an}"


class VeriKaynagi(Protocol):
    """Gercek entegrasyonun uygulayacagi arayuz."""

    def sorgula(self, metin: str) -> Yanit | None: ...


@dataclass(frozen=True, slots=True)
class Kayit:
    tur: IddiaTuru
    yetkili: str
    otomatik_kontrol: bool     # makinece dogrulanabilir mi
    hedef_sn: float            # cevap hedefi
    kaynak: Callable[[str], Yanit | None] | None = None
    mail: str = ""              # bildirim.py'nin mail atacagi kutu (simule adres)


# --- Simule veri kaynaklari -------------------------------------------------
# Her biri gercek bir API'nin yerini tutar. Donen degerler sabittir; amac
# boru hattinin uctan uca kosulabilmesidir.


def _dsi(metin: str) -> Yanit:
    return Yanit(
        dogrulandi=False,
        ozet="Su seviyesi 412 m (normal bant 405-418), kapaklar kapali, anomali yok.",
        kaynak="DSI telemetri",
        okuma_ts=time.time(),
    )


def _borsa(metin: str) -> Yanit:
    return Yanit(
        dogrulandi=False,
        ozet="BIST 100 seans ici degisim -%1,4. Devre kesici tetiklenmedi.",
        kaynak="Borsa Istanbul canli endeks",
        okuma_ts=time.time(),
    )


def _afad(metin: str) -> Yanit:
    return Yanit(
        dogrulandi=True,
        ozet="Bolgede 4,1 buyuklugunde artci kaydedildi. Yeni yikim bildirimi yok.",
        kaynak="AFAD + Kandilli",
        okuma_ts=time.time(),
    )


def _teias(metin: str) -> Yanit:
    return Yanit(
        dogrulandi=True,
        ozet="Bolgesel kesinti suruyor, tahmini onarim 6 saat.",
        kaynak="TEIAS kesinti servisi",
        okuma_ts=time.time(),
    )


# --- Kayit defteri ----------------------------------------------------------

KAYIT_DEFTERI: dict[IddiaTuru, Kayit] = {
    IddiaTuru.BARAJ: Kayit(
        IddiaTuru.BARAJ, "DSI", True, 30.0, _dsi, mail="dsi-izleme@ornek.gov.tr"
    ),
    IddiaTuru.FINANS: Kayit(
        IddiaTuru.FINANS, "Borsa Istanbul", True, 5.0, _borsa, mail="borsa-izleme@ornek.gov.tr"
    ),
    IddiaTuru.SISMIK: Kayit(
        IddiaTuru.SISMIK, "AFAD / Kandilli", True, 30.0, _afad, mail="afad-kandilli@ornek.gov.tr"
    ),
    IddiaTuru.ELEKTRIK: Kayit(
        IddiaTuru.ELEKTRIK, "TEIAS / EPDK", True, 60.0, _teias, mail="teias-ariza@ornek.gov.tr"
    ),
    IddiaTuru.DOGALGAZ: Kayit(
        IddiaTuru.DOGALGAZ, "BOTAS", True, 60.0, None, mail="botas-ariza@ornek.gov.tr"
    ),
    IddiaTuru.ULASIM: Kayit(
        IddiaTuru.ULASIM, "KGM", True, 60.0, None, mail="kgm-trafik@ornek.gov.tr"
    ),
    IddiaTuru.HAVA: Kayit(
        IddiaTuru.HAVA, "MGM", True, 30.0, None, mail="mgm-izleme@ornek.gov.tr"
    ),
    IddiaTuru.SAGLIK: Kayit(
        IddiaTuru.SAGLIK, "Saglik Bakanligi", False, 900.0, None, mail="sabim@ornek.gov.tr"
    ),
    IddiaTuru.ASAYIS: Kayit(
        IddiaTuru.ASAYIS,
        "Icisleri / Valilik",
        False,
        900.0,
        None,
        mail="valilik-koordinasyon@ornek.gov.tr",
    ),
    IddiaTuru.BILINMIYOR: Kayit(IddiaTuru.BILINMIYOR, "", False, 900.0, None, mail=""),
}


def yetkili_bul(tur: IddiaTuru) -> Kayit:
    return KAYIT_DEFTERI.get(tur, KAYIT_DEFTERI[IddiaTuru.BILINMIYOR])


def capraz_kontrol(tur: IddiaTuru, metin: str) -> Yanit | None:
    """Makinece dogrulanabilen iddialar icin otomatik cevap.

    None donerse iddia insan yetkiliye, sureli olarak dusurulur.
    """
    kayit = yetkili_bul(tur)
    if not kayit.otomatik_kontrol or kayit.kaynak is None:
        return None
    return kayit.kaynak(metin)

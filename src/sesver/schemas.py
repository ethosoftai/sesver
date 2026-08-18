"""Sistemin ortak veri sozlesmeleri.

Tum hatlar bu tiplerle konusur. Bagimlilik yok: stdlib dataclass yeterli,
boylece cekirdek pip install olmadan calisir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Mod(str, Enum):
    """Platformun genel durumu."""

    NORMAL = "normal"
    IZLEME = "izleme"
    AFET = "afet"
    SONUMLEME = "sonumleme"


class Tur(str, Enum):
    """Triyajin bir mesaj icin verdigi karar: hangi hatta gidecek."""

    CAGRI = "cagri"
    IDDIA = "iddia"
    DESTEK = "destek"
    GURULTU = "gurultu"


class Durum(str, Enum):
    """Bir gorevin yasam dongusu."""

    YENI = "yeni"
    DOGRULANIYOR = "dogrulaniyor"
    DOGRULANDI = "dogrulandi"
    EKIP_ATANDI = "ekip_atandi"
    KAPATILDI = "kapatildi"
    BAYAT = "bayat"
    ASILSIZ = "asilsiz"


class Alici(str, Enum):
    """Yonlendirme matrisinin hedefleri."""

    AFAD = "afad"
    SAHA_EKIBI = "saha_ekibi"
    VALILIK = "valilik"
    TEKNIK_KURUM = "teknik_kurum"
    SAGLIK = "saglik"
    KOLLUK = "kolluk"
    GONULLU = "gonullu"
    VATANDAS = "vatandas"
    KAMU = "kamu"
    GORENLERE_DUZELTME = "gorenlere_duzeltme"


class Cozunurluk(str, Enum):
    """Konumlandirmanin ne kadar keskin oldugu."""

    BINA = "bina"
    SOKAK = "sokak"
    MAHALLE = "mahalle"
    ILCE = "ilce"
    IL = "il"
    YOK = "yok"


@dataclass(slots=True)
class Hesap:
    """Mesaji atan hesabin dogrulamada ise yarayan meta verisi."""

    id: str
    yas_gun: int = 365
    takipci: int = 100
    bolgede_gecmis: bool = True
    gecmis_isabet: float | None = None

    @property
    def yeni_hesap(self) -> bool:
        return self.yas_gun < 7


@dataclass(slots=True)
class Mesaj:
    """Platformdan gelen ham olay."""

    id: str
    metin: str
    hesap: Hesap
    ts: float = field(default_factory=time.time)
    yanit_verilen: str | None = None
    paylasim: int = 0
    medya_parmak_izi: str | None = None
    konum_etiketi: tuple[float, float] | None = None

    @property
    def yanit_mi(self) -> bool:
        return self.yanit_verilen is not None


@dataclass(slots=True)
class Konum:
    il: str | None = None
    ilce: str | None = None
    mahalle: str | None = None
    sokak: str | None = None
    bina: str | None = None
    kat: int | None = None
    lat: float | None = None
    lon: float | None = None
    cozunurluk: Cozunurluk = Cozunurluk.YOK
    guven: float = 0.0

    def anahtar(self) -> str:
        """Tekillestirme icin kaba mekan anahtari."""
        parcalar = (self.il, self.ilce, self.mahalle, self.sokak, self.bina)
        return "|".join(str(x or "") for x in parcalar).lower()

    def bos_mu(self) -> bool:
        return self.cozunurluk is Cozunurluk.YOK


@dataclass(slots=True)
class Cagri:
    """A hatti: cikarimi yapilmis tek bir yardim cagrisi."""

    mesaj: Mesaj
    konum: Konum
    kisi_sayisi: int | None = None
    kirilgan: bool = False
    ses_var: bool = False
    aciklama: str = ""


@dataclass(slots=True)
class Gorev:
    """Tekillestirilmis olay: sahaya giden birim."""

    id: str
    konum: Konum
    cagrilar: list[Cagri] = field(default_factory=list)
    durum: Durum = Durum.YENI
    guven: float = 0.0
    oncelik: float = 0.0
    olusma_ts: float = field(default_factory=time.time)
    son_teyit_ts: float = field(default_factory=time.time)
    kapatma_sinyali: int = 0
    celiski: int = 0
    iz: list[str] = field(default_factory=list)

    @property
    def bagimsiz_kaynak(self) -> int:
        """Farkli hesaplardan gelen ihbar sayisi."""
        return len({c.mesaj.hesap.id for c in self.cagrilar})

    @property
    def kopya_sayisi(self) -> int:
        return max(0, len(self.cagrilar) - self.bagimsiz_kaynak)

    def yas_dk(self, simdi: float | None = None) -> float:
        # 0.0 gecerli bir zaman damgasidir; 'or' ile varsayilana dusulemez.
        an = time.time() if simdi is None else simdi
        return (an - self.son_teyit_ts) / 60.0


class IddiaTuru(str, Enum):
    """B hatti kayit defterindeki iddia siniflari."""

    BARAJ = "baraj"
    SISMIK = "sismik"
    FINANS = "finans"
    ELEKTRIK = "elektrik"
    DOGALGAZ = "dogalgaz"
    ULASIM = "ulasim"
    HAVA = "hava"
    SAGLIK = "saglik"
    ASAYIS = "asayis"
    BILINMIYOR = "bilinmiyor"


class KesiciDurum(str, Enum):
    KAPALI = "kapali"
    ACIK = "acik"
    COZULDU = "cozuldu"
    YANITSIZ = "yanitsiz"


@dataclass(slots=True)
class Iddia:
    """B hatti: genis etkili sistemik iddia."""

    id: str
    mesaj: Mesaj
    tur: IddiaTuru
    etki: float = 0.0
    yayilim_ivmesi: float = 0.0
    eylem_tetikleyici: bool = False
    kesici: KesiciDurum = KesiciDurum.KAPALI
    kesici_ts: float | None = None
    yetkili: str | None = None
    sonuc: str | None = None
    kaynak_damgasi: str | None = None
    goren_sayisi: int = 0
    iz: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Sevk:
    """Yonlendirme motorunun urettigi tek bir cikti paketi."""

    alici: Alici
    konu: str
    yuk: dict[str, Any]
    ts: float = field(default_factory=time.time)
    gerekce: str = ""

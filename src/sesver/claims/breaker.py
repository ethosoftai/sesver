"""Devre kesici - yayilimi yavaslatir, susturmaz.

Sistemin sansure donusmesini engelleyen dort kilit, kodda zorunlu tutulur:

  1. SILME YOK      - icerik durur, yalnizca oneri/kesfet akisindan cikar ve
                      paylasim oncesi surtunme gelir
  2. SURELI         - otomatik kesici en fazla ``kesici_azami_sn``; uzatma
                      insan onayi ister (``insan_uzatti``)
  3. SEFFAF         - her kesici karari kamuya acik gunluge yazilir
  4. YALNIZCA AFET  - normal modda mekanizma kapalidir

Borsalardan odunc alinmis bir fikirdir: fiyat cok hizli duserse islem
durdurulmaz, YAVASLATILIR; boylece panik ile bilgi birbirinden ayrilir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..config import ESIK
from ..schemas import Iddia, KesiciDurum, Mod


@dataclass(slots=True)
class GunlukKaydi:
    """Kamuya acik seffaflik gunlugunun tek satiri."""

    iddia_id: str
    tur: str
    etki: float
    acilis_ts: float
    kapanis_ts: float | None = None
    sonuc: str | None = None
    insan_onayi: bool = False

    @property
    def sure_sn(self) -> float | None:
        return None if self.kapanis_ts is None else self.kapanis_ts - self.acilis_ts


class DevreKesici:
    def __init__(self, mod: Mod = Mod.AFET) -> None:
        self.mod = mod
        self.gunluk: list[GunlukKaydi] = []

    # --- karar ---

    def tetiklenmeli_mi(self, iddia: Iddia) -> bool:
        if self.mod is not Mod.AFET:
            return False          # kilit 4: yalnizca afet modunda
        return iddia.etki >= ESIK.kesici_etki_esigi

    def ac(self, iddia: Iddia, simdi: float | None = None) -> bool:
        if not self.tetiklenmeli_mi(iddia):
            return False
        simdi = time.time() if simdi is None else simdi
        iddia.kesici = KesiciDurum.ACIK
        iddia.kesici_ts = simdi
        iddia.iz.append(f"kesici acildi (etki={iddia.etki})")
        self.gunluk.append(
            GunlukKaydi(
                iddia_id=iddia.id, tur=iddia.tur.value, etki=iddia.etki, acilis_ts=simdi
            )
        )
        return True

    def suresi_doldu_mu(self, iddia: Iddia, simdi: float | None = None) -> bool:
        if iddia.kesici is not KesiciDurum.ACIK or iddia.kesici_ts is None:
            return False
        an = time.time() if simdi is None else simdi
        return an - iddia.kesici_ts > ESIK.kesici_azami_sn

    def coz(self, iddia: Iddia, sonuc: str, damga: str, simdi: float | None = None) -> None:
        """Yetkili cevap geldi: kesici kapanir, sonuc kaydedilir."""
        simdi = time.time() if simdi is None else simdi
        iddia.kesici = KesiciDurum.COZULDU
        iddia.sonuc = sonuc
        iddia.kaynak_damgasi = damga
        iddia.iz.append(f"cozuldu: {damga}")
        self._gunlugu_kapat(iddia, simdi, sonuc)

    def yanitsiz(self, iddia: Iddia, simdi: float | None = None) -> None:
        """Kurum suresinde donmedi. Kesici otomatik olarak DUSER.

        Sessizlik, yayilimi kalici olarak kisitlamanin gerekcesi olamaz.
        Bunun yerine durum kamuya "yanitsiz" olarak gorunur; bu, kurumu da
        hesap verebilir kilar.
        """
        simdi = time.time() if simdi is None else simdi
        iddia.kesici = KesiciDurum.YANITSIZ
        iddia.iz.append("yetkili suresinde yanit vermedi, kesici dustu")
        self._gunlugu_kapat(iddia, simdi, "yanitsiz")

    def insan_uzatti(self, iddia: Iddia, gerekce: str) -> None:
        """15 dakikayi asan her kisitlama insan onayi gerektirir (kilit 2)."""
        iddia.iz.append(f"insan onayiyla uzatildi: {gerekce}")
        for kayit in self.gunluk:
            if kayit.iddia_id == iddia.id and kayit.kapanis_ts is None:
                kayit.insan_onayi = True

    # --- seffaflik ---

    def _gunlugu_kapat(self, iddia: Iddia, simdi: float, sonuc: str) -> None:
        for kayit in self.gunluk:
            if kayit.iddia_id == iddia.id and kayit.kapanis_ts is None:
                kayit.kapanis_ts = simdi
                kayit.sonuc = sonuc

    def seffaflik_raporu(self) -> list[dict]:
        """Kamuya acik gunluk. Her kesici karari, gerekcesi ve suresiyle."""
        return [
            {
                "iddia_id": k.iddia_id,
                "tur": k.tur,
                "etki": k.etki,
                "sure_sn": round(k.sure_sn, 1) if k.sure_sn is not None else None,
                "sonuc": k.sonuc,
                "insan_onayi": k.insan_onayi,
            }
            for k in self.gunluk
        ]

"""Boru hatti orkestratoru.

Neden genel amacli bir ajan cercevesi degil de tipli bir durum grafigi?

Uc gerekce:
  1. BELIRLENIMCILIK - ayni girdi ayni cikti. Bir kurtarma sisteminde kararin
     yeniden uretilebilir olmasi zorunludur.
  2. DENETLENEBILIRLIK - her asamanin suresi ve her kararin gerekcesi ize
     yazilir. "Neden bu gorev ust siradaydi" sorusunun cevabi kayitlidir.
  3. ARIZA DAVRANISI - bir asama patlarsa hat susmaz; o asama atlanir ve
     kayit ham haliyle akmaya devam eder (fail-open).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..bildirim import Bildirimci
from ..claims.backprop import GeriYayilim, YayilimAgaci
from ..claims.breaker import DevreKesici
from ..claims.detect import IddiaTespitci
from ..claims.impact import etki_hesapla
from ..claims.registry import capraz_kontrol, yetkili_bul
from ..schemas import Gorev, Iddia, Mesaj, Mod, Sevk, Tur
from .close import Kapatici
from .dedup import Birlestirici
from .extract import Cozumleyici
from .prioritize import Onceliklendirici
from .route import Yonlendirici
from .triage import KuralTriyaj, Triyajci
from .verify import Dogrulayici


@dataclass(slots=True)
class Sayaclar:
    mesaj: int = 0
    cagri: int = 0
    iddia: int = 0
    destek: int = 0
    gurultu: int = 0
    yanit: int = 0
    konumsuz: int = 0
    kesici_acilan: int = 0
    kesici_cozulen: int = 0
    asama_sn: dict[str, float] = field(default_factory=dict)

    def sure_ekle(self, asama: str, sn: float) -> None:
        self.asama_sn[asama] = self.asama_sn.get(asama, 0.0) + sn


class BoruHatti:
    """Uctan uca akis isleyici.

    Kullanim::

        hat = BoruHatti()
        for mesaj in akis:
            hat.isle(mesaj)
        kuyruk = hat.kuyruk()
    """

    def __init__(
        self,
        triyaj: Triyajci | None = None,
        mod: Mod = Mod.AFET,
        bildirimci: Bildirimci | None = None,
    ) -> None:
        self.mod = mod
        self.triyaj = triyaj or KuralTriyaj()
        self.cozumleyici = Cozumleyici()
        self.birlestirici = Birlestirici()
        self.dogrulayici = Dogrulayici()
        self.onceliklendirici = Onceliklendirici()
        self.kapatici = Kapatici()
        self.yonlendirici = Yonlendirici()
        self.bildirimci = bildirimci or Bildirimci()

        self.iddia_tespitci = IddiaTespitci()
        self.kesici = DevreKesici(mod=mod)
        self.geri_yayilim = GeriYayilim()

        self.sayac = Sayaclar()
        self.iddialar: dict[str, Iddia] = {}
        self.sevkler: list[Sevk] = []
        self.son_ts: float = 0.0

    # --- akis girisi ---

    def isle(self, mesaj: Mesaj) -> None:
        self.sayac.mesaj += 1
        self.son_ts = max(self.son_ts, mesaj.ts)

        # Yanitlar dogrulama katmanini besler, kendi basina gorev acmaz.
        if mesaj.yanit_mi:
            self.sayac.yanit += 1
            self.dogrulayici.yanit_ekle(mesaj)
            return

        t = time.perf_counter()
        tur, _ = self.triyaj(mesaj)
        self.sayac.sure_ekle("triyaj", time.perf_counter() - t)

        if tur is Tur.CAGRI:
            self._cagri_isle(mesaj)
        elif tur is Tur.IDDIA:
            self._iddia_isle(mesaj)
        elif tur is Tur.DESTEK:
            self.sayac.destek += 1
        else:
            self.sayac.gurultu += 1

    # --- A hatti ---

    def _cagri_isle(self, mesaj: Mesaj) -> None:
        self.sayac.cagri += 1
        t = time.perf_counter()
        cagri = self.cozumleyici(mesaj)
        self.sayac.sure_ekle("cozumleme", time.perf_counter() - t)

        t = time.perf_counter()
        gorev = self.birlestirici.ekle(cagri)
        self.sayac.sure_ekle("birlestirme", time.perf_counter() - t)
        if gorev is None:
            # Adres cozulemedi: gorev kuyruguna girmez, gonullu zenginlestirmesine duser.
            self.sayac.konumsuz += 1

    # --- B hatti ---

    def _iddia_isle(self, mesaj: Mesaj) -> None:
        self.sayac.iddia += 1
        iddia = self.iddia_tespitci(mesaj)
        if iddia is None:
            self.sayac.gurultu += 1
            return

        self.iddialar[iddia.id] = iddia
        paylasim_dk = mesaj.paylasim / 10.0
        etki_hesapla(iddia, paylasim_dk)

        if self.kesici.ac(iddia, simdi=mesaj.ts):
            self.sayac.kesici_acilan += 1
            self.bildirimci.iddia_tespit_edildi(iddia)

        kayit = yetkili_bul(iddia.tur)
        iddia.yetkili = kayit.yetkili or None

        yanit = capraz_kontrol(iddia.tur, mesaj.metin)
        if yanit is not None:
            self.kesici.coz(iddia, yanit.ozet, yanit.damga, simdi=mesaj.ts + kayit.hedef_sn)
            self.sayac.kesici_cozulen += 1
            self.bildirimci.iddia_sonuclandi(iddia)
            agac = YayilimAgaci(kok_mesaj=mesaj.id)
            for i in range(max(mesaj.paylasim, 1) * 20):
                agac.goster(f"{mesaj.id}-u{i}")
            for i in range(mesaj.paylasim):
                agac.paylas(f"{mesaj.id}-u{i}")
            self.geri_yayilim.dagit(iddia, agac)

        self.sevkler.extend(self.yonlendirici.iddia_sevkleri(iddia))

    # --- cikti ---

    def kuyruk(self, simdi: float | None = None) -> list[Gorev]:
        """Dogrulanmis, kapatilmis ve onceliklendirilmis gorev listesi."""
        simdi = simdi if simdi is not None else (self.son_ts or time.time())
        gorevler = list(self.birlestirici.gorevler.values())

        t = time.perf_counter()
        for g in gorevler:
            self.dogrulayici(g)
            self.kapatici(g, simdi)
        self.sayac.sure_ekle("dogrulama", time.perf_counter() - t)

        t = time.perf_counter()
        sirali = self.onceliklendirici(gorevler, simdi)
        self.sayac.sure_ekle("onceliklendirme", time.perf_counter() - t)

        for g in sirali:
            self.bildirimci.gorev_yuksek_oncelik(g)

        return sirali

    def tum_sevkler(self, simdi: float | None = None) -> list[Sevk]:
        sevkler = list(self.sevkler)
        for gorev in self.kuyruk(simdi):
            sevkler.extend(self.yonlendirici.gorev_sevkleri(gorev))
        return sevkler

    def ozet(self) -> dict:
        s = self.sayac
        return {
            "mesaj": s.mesaj,
            "yanit": s.yanit,
            "cagri": s.cagri,
            "iddia": s.iddia,
            "destek": s.destek,
            "gurultu": s.gurultu,
            "konumsuz": s.konumsuz,
            "gorev": len(self.birlestirici.gorevler),
            "kesici_acilan": s.kesici_acilan,
            "kesici_cozulen": s.kesici_cozulen,
            "mail_gonderilen": sum(1 for k in self.bildirimci.gunluk if k.basarili),
            "mail_basarisiz": sum(1 for k in self.bildirimci.gunluk if not k.basarili),
            "asama_sn": {k: round(v, 4) for k, v in s.asama_sn.items()},
        }

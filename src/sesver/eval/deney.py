"""Deney kosumlari: coklu tohum, bilesen ablasyonu, esik duyarliligi.

Tek bir kosumdan elde edilen nokta tahmin, bir muhendislik iddiasini
tasiyamaz: tohum degisince sayi da degisir ve okuyucu bunun ne kadarinin
sistemden, ne kadarinin sanstan geldigini bilemez. Bu modul uc soruyu
olculebilir hale getirir:

  1. COKLU TOHUM     - sonuclar ne kadar kararli? (ortalama +/- guven araligi)
  2. ABLASYON        - her bilesen gercekten yerini hak ediyor mu?
  3. ESIK DUYARLILIGI - sonuclar sansli bir esik secimine mi dayaniyor?

Ablasyonlar, uretim kodunu DEGISTIRMEDEN, bilesenlerin devre disi birakilmis
alt siniflari uzerinden kosar. Boylece "olcum icin acilan bir kapi" uretimde
kalmis olmaz.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import ESIK, Esikler
from ..data.synth import AkisUreteci
from ..pipeline.dedup import Birlestirici
from ..pipeline.graph import BoruHatti
from ..pipeline.verify import Dogrulayici
from ..schemas import Durum
from .bench import _gorev_olaylari, _triyaj_metrigi

# --------------------------------------------------------------------------
# Olcum
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Olcum:
    """Bir kosumun ozet metrikleri."""

    anma: float
    kacan: int
    oran: float
    saflik: float
    kapsama: float
    bayat_kapatma: float
    gorev: int
    mesaj_sn: float
    # Durus ve ucgenleme kumelemeyi degil GUVENI etkiler; etkileri ancak
    # asagidaki iki metrikte gorunur.
    dogrulanan: int          # DOGRULANDI durumuna ulasan gorev sayisi
    sahte_medyan: float      # sahte gorevlerin kuyruktaki medyan yuzdeligi


def _olc(akis, hat: BoruHatti, kuyruk, sure: float) -> Olcum:
    ozet = hat.ozet()
    saf = toplam = 0
    yakalanan: set[str] = set()
    for g in hat.birlestirici.gorevler.values():
        olaylar = _gorev_olaylari(g, akis)
        if not olaylar:
            continue
        toplam += 1
        yakalanan |= olaylar
        if len(olaylar) == 1:
            saf += 1

    cozulmus = {o.id for o in akis.olaylar.values() if o.cozuldu}
    kapatilan = sum(
        1 for g in kuyruk
        if g.durum is Durum.KAPATILDI and _gorev_olaylari(g, akis) & cozulmus
    )
    # Sahte gorevlerin kuyruktaki konumu: bastirma kalitesi
    n = max(len(kuyruk), 1)
    sahte_y = []
    dogrulanan = 0
    for sira, g in enumerate(kuyruk):
        if g.durum is Durum.DOGRULANDI:
            dogrulanan += 1
        olaylar = _gorev_olaylari(g, akis)
        if olaylar and all(not akis.olaylar[o].gercek for o in olaylar):
            sahte_y.append(sira / n)

    t = _triyaj_metrigi(akis, hat)
    return Olcum(
        anma=t.anma,
        kacan=t.kacan,
        oran=ozet["cagri"] / max(ozet["gorev"], 1),
        saflik=saf / max(toplam, 1),
        kapsama=len(yakalanan) / max(len(akis.olaylar), 1),
        bayat_kapatma=kapatilan / max(len(cozulmus), 1),
        gorev=ozet["gorev"],
        mesaj_sn=ozet["mesaj"] / max(sure, 1e-9),
        dogrulanan=dogrulanan,
        sahte_medyan=statistics.median(sahte_y) if sahte_y else 1.0,
    )


def _kosum(mesaj_sayisi: int, seed: int, hat_kur: Callable[[], BoruHatti],
           gurultu: float = 1.0) -> Olcum:
    import time

    akis = AkisUreteci(seed=seed, gurultu_siddeti=gurultu).uret(mesaj_sayisi)
    hat = hat_kur()
    t0 = time.perf_counter()
    for m in akis.mesajlar:
        hat.isle(m)
    kuyruk = hat.kuyruk()
    return _olc(akis, hat, kuyruk, time.perf_counter() - t0)


# --------------------------------------------------------------------------
# 1. Coklu tohum
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Ozet:
    """Ortalama, standart sapma ve %95 guven araligi."""

    ad: str
    degerler: list[float] = field(default_factory=list)

    @property
    def ortalama(self) -> float:
        return statistics.fmean(self.degerler)

    @property
    def sapma(self) -> float:
        return statistics.stdev(self.degerler) if len(self.degerler) > 1 else 0.0

    @property
    def guven_araligi(self) -> tuple[float, float]:
        """t dagilimi ile %95 GA. Kucuk ornek sayisi icin t katsayilari."""
        n = len(self.degerler)
        if n < 2:
            return (self.ortalama, self.ortalama)
        t95 = {2: 12.71, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571,
               7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}.get(n - 1, 1.96)
        pay = t95 * self.sapma / math.sqrt(n)
        return (self.ortalama - pay, self.ortalama + pay)

    def yaz(self, basamak: int = 4) -> str:
        alt, ust = self.guven_araligi
        return (f"{self.ortalama:.{basamak}f} ± {ust - self.ortalama:.{basamak}f}"
                f"  [{alt:.{basamak}f}, {ust:.{basamak}f}]")


def coklu_tohum(mesaj_sayisi: int = 20_000, tohumlar: tuple[int, ...] = (7, 11, 23, 42, 101),
                gurultu: float = 1.0) -> dict[str, Ozet]:
    """Ayni yapilandirmayi farkli tohumlarla kosar."""
    alanlar = ("anma", "kacan", "oran", "saflik", "kapsama",
               "bayat_kapatma", "mesaj_sn")
    ozetler = {a: Ozet(a) for a in alanlar}
    for s in tohumlar:
        o = _kosum(mesaj_sayisi, s, BoruHatti, gurultu)
        for a in alanlar:
            ozetler[a].degerler.append(float(getattr(o, a)))
    return ozetler


# --------------------------------------------------------------------------
# 2. Bilesen ablasyonu
# --------------------------------------------------------------------------


class _TekillestirmeYok(Birlestirici):
    """Her cagri kendi gorevini acar."""

    def _en_iyi_eslesme(self, cagri):
        return None


class _AdresUyumlulukYok(Birlestirici):
    """Adres celiskisi yok sayilir; yalnizca metin benzerligine bakilir.

    Bu, duzeltilmeden onceki hatali davranistir. Ablasyon, o hatanin
    maliyetini sayisal olarak gosterir.
    """

    @staticmethod
    def _uyumlu(a, b) -> bool:
        return True


class _KonumsuzHavuzYok(Birlestirici):
    """Adresi cozulemeyen cagrilar da gorev kuyruguna girer."""

    def ekle(self, cagri):
        if cagri.konum.bos_mu():
            from itertools import count as _c
            if not hasattr(self, "_bos_sayac"):
                self._bos_sayac = _c(900_000)
            from ..schemas import Gorev
            g = Gorev(id=f"G-{next(self._bos_sayac)}", konum=cagri.konum,
                      olusma_ts=cagri.mesaj.ts, son_teyit_ts=cagri.mesaj.ts)
            g.cagrilar.append(cagri)
            self.gorevler[g.id] = g
            return g
        return super().ekle(cagri)


class _DurusYok(Dogrulayici):
    """Yanit zinciri sinyali kullanilmaz."""

    def yanit_ekle(self, yanit) -> None:
        return None


class _UcgenlemeYok(Dogrulayici):
    """Bagimsiz kaynak sayisi guveni etkilemez."""

    def __call__(self, gorev):
        gorev = super().__call__(gorev)
        # Ucgenleme katkisini geri al: tek kaynakli gibi yeniden puanla.
        gorev.guven = max(0.0, gorev.guven - 0.33)
        if gorev.guven < ESIK.guven_alt:
            gorev.durum = Durum.YENI
        return gorev


def _hat(birlestirici=None, dogrulayici=None, esik: Esikler | None = None):
    def kur() -> BoruHatti:
        h = BoruHatti()
        if birlestirici is not None:
            h.birlestirici = birlestirici()
        if dogrulayici is not None:
            h.dogrulayici = dogrulayici()
        return h
    return kur


ABLASYONLAR: dict[str, Callable[[], BoruHatti]] = {
    "tam sistem": BoruHatti,
    "tekillestirme yok": _hat(birlestirici=_TekillestirmeYok),
    "adres uyumlulugu yok": _hat(birlestirici=_AdresUyumlulukYok),
    "konumsuz havuz yok": _hat(birlestirici=_KonumsuzHavuzYok),
    "durus analizi yok": _hat(dogrulayici=_DurusYok),
    "ucgenleme yok": _hat(dogrulayici=_UcgenlemeYok),
}


def ablasyon(mesaj_sayisi: int = 10_000,
             tohumlar: tuple[int, ...] = (7, 23, 42)) -> dict[str, dict[str, Ozet]]:
    sonuc: dict[str, dict[str, Ozet]] = {}
    alanlar = ("saflik", "oran", "kacan", "bayat_kapatma", "kapsama",
               "gorev", "dogrulanan", "sahte_medyan")
    for ad, kur in ABLASYONLAR.items():
        ozetler = {a: Ozet(a) for a in alanlar}
        for s in tohumlar:
            o = _kosum(mesaj_sayisi, s, kur)
            for a in alanlar:
                ozetler[a].degerler.append(float(getattr(o, a)))
        sonuc[ad] = ozetler
    return sonuc


# --------------------------------------------------------------------------
# 3. Esik duyarliligi
# --------------------------------------------------------------------------


def esik_duyarliligi(mesaj_sayisi: int = 10_000, seed: int = 7,
                     degerler=(0.60, 0.66, 0.72, 0.78, 0.84, 0.90)) -> list[dict]:
    """Metin benzerligi esigini tarar.

    Amac, raporlanan sonucun sansli bir esik secimine dayanmadigini
    gostermektir. Esik dusukse farkli olaylar birlesir (saflik duser),
    yuksekse ayni olay bolunur (indirgeme duser).
    """
    import dataclasses

    asil = ESIK.metin_benzerlik
    egri = []
    try:
        for v in degerler:
            yeni = dataclasses.replace(ESIK, metin_benzerlik=v)
            import sesver.config as _cfg
            import sesver.pipeline.dedup as _dedup
            _cfg.ESIK = yeni
            _dedup.ESIK = yeni
            o = _kosum(mesaj_sayisi, seed, BoruHatti)
            egri.append({"esik": v, "saflik": round(o.saflik, 4),
                         "oran": round(o.oran, 2), "gorev": o.gorev,
                         "kapsama": round(o.kapsama, 4)})
    finally:
        import dataclasses as _dc

        import sesver.config as _cfg
        import sesver.pipeline.dedup as _dedup
        geri = _dc.replace(ESIK, metin_benzerlik=asil)
        _cfg.ESIK = geri
        _dedup.ESIK = geri
    return egri


# --------------------------------------------------------------------------
# 4. Hata analizi
# --------------------------------------------------------------------------


def karisiklik_matrisi(mesaj_sayisi: int = 12_000, seed: int = 303,
                       sablon_yarisi: str = "b") -> dict:
    """Egitilmis triyaj modelinin karisiklik matrisi ve hata taksonomisi.

    Toplam skor, hangi hatanin yapildigini gizler. Afet baglaminda
    "cagri -> gurultu" ile "gurultu -> cagri" ayni buyuklukte iki hata
    degildir; birincisi bir aileyi kaybettirir, ikincisi bir satir gurultu
    ekler. Matris bu ayrimi gorunur kilar.
    """
    from ..models.ayikla import SINIFLAR, OrtalamaPerceptron, varsayilan_model_yolu
    from ..models.egit_ayikla import ornekler

    model = OrtalamaPerceptron.yukle(varsayilan_model_yolu())
    veri = ornekler(mesaj_sayisi, seed=seed, sablon_yarisi=sablon_yarisi)

    matris = {g: dict.fromkeys(SINIFLAR, 0) for g in SINIFLAR}
    ornek_hatalar: dict[str, list[str]] = {}
    for metin, gercek in veri:
        tahmin = model.tahmin(metin)[0]
        matris[gercek][tahmin] += 1
        if tahmin != gercek:
            anahtar = f"{gercek} -> {tahmin}"
            if len(ornek_hatalar.setdefault(anahtar, [])) < 4:
                ornek_hatalar[anahtar].append(metin[:110])

    return {
        "n": len(veri),
        "matris": matris,
        "ornek_hatalar": dict(sorted(
            ornek_hatalar.items(),
            key=lambda kv: -sum(matris[kv[0].split(" -> ")[0]].values()),
        )),
    }

"""SES VER-Bench: yer gercegine karsi uctan uca degerlendirme.

Kosum, sentetik akisi uretir, boru hattini calistirir ve her metrigi
yer gercegiyle karsilastirir. Hicbir sayi elle girilmez; raporda ne
yaziyorsa burasi uretir.
"""

from __future__ import annotations

import statistics
import time

from ..data.synth import Akis, AkisUreteci
from ..pipeline.graph import BoruHatti
from ..schemas import Durum, Tur
from .metrics import (
    BastirmaMetrik,
    HizMetrik,
    Rapor,
    TazelikMetrik,
    TekillestirmeMetrik,
    TriyajMetrik,
)


def _triyaj_metrigi(akis: Akis, hat: BoruHatti) -> TriyajMetrik:
    """Gercek cagri mesajlarinin kaci CAGRI olarak siniflandi."""
    dogru_pozitif = yanlis_negatif = yanlis_pozitif = 0
    for m in akis.mesajlar:
        if m.yanit_mi:
            continue
        gercek_cagri = m.id in akis.mesaj_olay
        tahmin, _ = hat.triyaj(m)
        if gercek_cagri and tahmin is Tur.CAGRI:
            dogru_pozitif += 1
        elif gercek_cagri:
            yanlis_negatif += 1
        elif tahmin is Tur.CAGRI:
            yanlis_pozitif += 1

    anma = dogru_pozitif / max(dogru_pozitif + yanlis_negatif, 1)
    kesinlik = dogru_pozitif / max(dogru_pozitif + yanlis_pozitif, 1)
    f1 = 2 * anma * kesinlik / max(anma + kesinlik, 1e-9)
    return TriyajMetrik(
        anma=round(anma, 4),
        kesinlik=round(kesinlik, 4),
        f1=round(f1, 4),
        kacan=yanlis_negatif,
    )


def _gorev_olaylari(gorev, akis: Akis) -> set[str]:
    return {akis.mesaj_olay[c.mesaj.id] for c in gorev.cagrilar if c.mesaj.id in akis.mesaj_olay}


def kosum(mesaj_sayisi: int = 20_000, seed: int = 7, saat: float = 12.0) -> tuple[Rapor, list]:
    akis = AkisUreteci(seed=seed).uret(mesaj_sayisi, saat=saat)
    hat = BoruHatti()

    t0 = time.perf_counter()
    for m in akis.mesajlar:
        hat.isle(m)
    kuyruk = hat.kuyruk()
    sure = time.perf_counter() - t0

    ozet = hat.ozet()

    # --- tekillestirme ---
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

    tekil = TekillestirmeMetrik(
        cagri=ozet["cagri"],
        gorev=ozet["gorev"],
        oran=round(ozet["cagri"] / max(ozet["gorev"], 1), 2),
        saflik=round(saf / max(toplam, 1), 4),
        kapsama=round(len(yakalanan) / max(len(akis.olaylar), 1), 4),
        konumsuz=ozet["konumsuz"],
    )

    # --- bastirma: sahte gorevler kuyrugun neresinde ---
    n = max(len(kuyruk), 1)
    sahte_yuzdelik: list[float] = []
    sahte_ilk_100 = 0
    gercek_kaybi = 0
    for sira, g in enumerate(kuyruk):
        olaylar = _gorev_olaylari(g, akis)
        if not olaylar:
            continue
        sahte = all(not akis.olaylar[o].gercek for o in olaylar)
        if sahte:
            yuzdelik = sira / n
            sahte_yuzdelik.append(yuzdelik)
            if sira < 100:
                sahte_ilk_100 += 1
        elif g.durum is Durum.ASILSIZ:
            # Gercek bir gorev asilsiz damgasi yemis olmamali.
            gercek_kaybi += 1

    bastirma = BastirmaMetrik(
        sahte_gorev=len(sahte_yuzdelik),
        sahte_ilk_100=sahte_ilk_100,
        sahte_medyan_yuzdelik=round(statistics.median(sahte_yuzdelik), 3)
        if sahte_yuzdelik
        else 1.0,
        gercek_kaybi=gercek_kaybi,
    )

    # --- tazelik ---
    cozulmus = {o.id for o in akis.olaylar.values() if o.cozuldu}
    kapatilan = 0
    for g in kuyruk:
        if g.durum is Durum.KAPATILDI and _gorev_olaylari(g, akis) & cozulmus:
            kapatilan += 1
    tazelik = TazelikMetrik(
        cozulmus_olay=len(cozulmus),
        kapatilan=kapatilan,
        kapatma_orani=round(kapatilan / max(len(cozulmus), 1), 4),
    )

    hiz = HizMetrik(
        mesaj=ozet["mesaj"],
        sure_sn=round(sure, 3),
        mesaj_sn=round(ozet["mesaj"] / max(sure, 1e-9), 1),
        asama_sn=ozet["asama_sn"],
    )

    rapor = Rapor(
        triyaj=_triyaj_metrigi(akis, hat),
        tekillestirme=tekil,
        bastirma=bastirma,
        tazelik=tazelik,
        hiz=hiz,
        kesici_acilan=ozet["kesici_acilan"],
        kesici_cozulen=ozet["kesici_cozulen"],
    )
    return rapor, kuyruk

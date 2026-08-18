"""Etki skoru: bir iddianin patlama yaricapi.

Uc carpanin bilesimi:

  1. TABAN     - iddia turunun dogasi geregi kac kisiyi ilgilendirdigi
  2. IVME      - yayilimin dakikalik turevi; organik virali panikten ayirir
  3. EYLEM     - insanlari fiziksel harekete gecirip gecirmedigi

Ucuncusu en kritigidir. "Baraj su seviyesi yuksek" ile "Baraj patladi, herkes
yuksek yere kacsin" ayni bilgiyi tasir ama ikincisi trafigi kilitler, kurtarma
araclarinin gecisini engeller ve izdiham riski yaratir. Kesici eylem tetikleyen
iddiada daha erken devreye girer.
"""

from __future__ import annotations

from ..config import ESIK
from ..schemas import Iddia, IddiaTuru

# Turun dogal patlama yaricapi (0-1).
TUR_TABANI: dict[IddiaTuru, float] = {
    IddiaTuru.BARAJ: 0.95,      # yanlissa izdiham, dogruysa tahliye
    IddiaTuru.SISMIK: 0.80,
    IddiaTuru.DOGALGAZ: 0.78,
    IddiaTuru.SAGLIK: 0.72,
    IddiaTuru.FINANS: 0.68,     # banka hucumu gercek bir risktir
    IddiaTuru.ULASIM: 0.62,
    IddiaTuru.ELEKTRIK: 0.55,
    IddiaTuru.ASAYIS: 0.70,     # yagma soylentisi guvenlik kaynagini saptirir
    IddiaTuru.HAVA: 0.50,
    IddiaTuru.BILINMIYOR: 0.30,
}


def ivme_normalize(paylasim_dk: float) -> float:
    """Dakikadaki paylasim turevini 0-1 bandina sikistirir."""
    if paylasim_dk <= 0:
        return 0.0
    return min(paylasim_dk / (ESIK.ivme_esigi * 100.0), 1.0)


def etki_hesapla(iddia: Iddia, paylasim_dk: float = 0.0) -> float:
    taban = TUR_TABANI[iddia.tur]
    ivme = ivme_normalize(paylasim_dk)
    skor = 0.55 * taban + 0.30 * ivme
    if iddia.eylem_tetikleyici:
        skor += 0.20
    iddia.yayilim_ivmesi = round(ivme, 3)
    iddia.etki = round(min(skor, 1.0), 3)
    return iddia.etki

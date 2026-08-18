"""Geri yayilim - duzeltmeyi, soylentinin gittigi yoldan geri gonderir.

Duzeltmenin klasik problemi yanlis kitleye ulasmasidir: soylentiyi iki yuz bin
kisi gorur, duzeltmeyi dort bin kisi. Platform, yayilim grafigini zaten elinde
tuttugu icin duzeltmeyi TAM OLARAK o iki yuz bin kisiye gonderebilir.

Burada olculen sey "erisim" degil, KAPSAMA: soylentiyi gorenlerin yuzde kaci
duzeltmeyi de gordu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import Iddia


@dataclass(slots=True)
class YayilimAgaci:
    """Bir iddianin kimlere ulastigini tutar.

    Gercek platformda bu, oneri servisinin gosterim kayitlarindan gelir.
    Burada acik bir veri yapisi olarak modellenir ki kapsama olculebilsin.
    """

    kok_mesaj: str
    gorenler: set[str] = field(default_factory=set)
    paylasanlar: set[str] = field(default_factory=set)

    def goster(self, hesap_id: str) -> None:
        self.gorenler.add(hesap_id)

    def paylas(self, hesap_id: str) -> None:
        self.paylasanlar.add(hesap_id)
        self.gorenler.add(hesap_id)


@dataclass(slots=True)
class DuzeltmeSonucu:
    hedef: int
    ulasilan: int
    kapsama: float
    paylasanlara_ulasan: int

    def ozet(self) -> str:
        return (
            f"{self.ulasilan}/{self.hedef} kisi ({self.kapsama:.0%}), "
            f"paylasanlarin {self.paylasanlara_ulasan} tanesi bilgilendirildi"
        )


class GeriYayilim:
    """Duzeltmeyi yayilim agaci uzerinden dagitir."""

    def __init__(self, ulasim_orani: float = 0.94) -> None:
        # Gercek sistemde bu oran bildirim acilma istatistiginden gelir.
        # Varsayilan, gosterimi garanti olan akis ici kart yerlesimini varsayar.
        self.ulasim_orani = ulasim_orani

    def dagit(self, iddia: Iddia, agac: YayilimAgaci) -> DuzeltmeSonucu:
        hedef = len(agac.gorenler)
        ulasilan = int(hedef * self.ulasim_orani)
        paylasan = int(len(agac.paylasanlar) * self.ulasim_orani)
        iddia.goren_sayisi = hedef
        iddia.iz.append(f"geri yayilim: {ulasilan}/{hedef} kisi")
        return DuzeltmeSonucu(
            hedef=hedef,
            ulasilan=ulasilan,
            kapsama=(ulasilan / hedef) if hedef else 0.0,
            paylasanlara_ulasan=paylasan,
        )

"""Adres sozlugu: mahalle adindan koordinata.

Uretimde bu katmanin arkasinda UAVT (Ulusal Adres Veri Tabani) ve bina
envanteri durur. Repoda, kosumun disariya bagimli olmamasi icin kucuk bir
ornek sozluk bulunur; arayuz ayni kalir.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..metin import normalize, yakin_esles

VARSAYILAN = Path(__file__).resolve().parents[3] / "data" / "gazetteer_ornek.json"


class Gazetteer:
    def __init__(self, yol: Path | str | None = None) -> None:
        self.yol = Path(yol) if yol else VARSAYILAN
        with open(self.yol, encoding="utf-8") as f:
            self._ham = json.load(f)
        self._iller = self._ham["iller"]
        self._barajlar = self._ham.get("barajlar", {})
        self._duz: dict[str, tuple[str, str, str, float, float]] = {}
        for il, ilv in self._iller.items():
            for ilce, ilcev in ilv["ilceler"].items():
                for mah, koord in ilcev["mahalleler"].items():
                    self._duz[normalize(mah)] = (il, ilce, mah, koord[0], koord[1])

    # --- sorgular ---

    @property
    def mahalleler(self) -> list[str]:
        return [v[2] for v in self._duz.values()]

    @property
    def ilceler(self) -> list[str]:
        return [ilce for ilv in self._iller.values() for ilce in ilv["ilceler"]]

    @property
    def iller(self) -> list[str]:
        return list(self._iller)

    def mahalle_ara(self, ad: str) -> tuple[str, str, str, float, float] | None:
        """Yazim hatasina toleransli mahalle cozumlemesi."""
        anahtar = normalize(ad)
        if anahtar in self._duz:
            return self._duz[anahtar]
        eslesme = yakin_esles(ad, self.mahalleler)
        return self._duz[normalize(eslesme)] if eslesme else None

    def ilce_merkez(self, ilce: str) -> tuple[str, str, float, float] | None:
        hedef = yakin_esles(ilce, self.ilceler)
        if not hedef:
            return None
        for il, ilv in self._iller.items():
            if hedef in ilv["ilceler"]:
                m = ilv["ilceler"][hedef]["merkez"]
                return (il, hedef, m[0], m[1])
        return None

    def baraj_ara(self, metin: str) -> tuple[str, dict] | None:
        n = normalize(metin)
        for ad, kayit in self._barajlar.items():
            if normalize(ad).split()[0] in n:
                return ad, kayit
        return None


@lru_cache(maxsize=1)
def varsayilan_gazetteer() -> Gazetteer:
    return Gazetteer()

"""B hatti tespiti: akistan sistemik IDDIA cikarir ve turunu belirler.

Ayrim onemlidir: "baraj" tek basina bir haberdir, "baraj patladi" bir
iddiadir. Bu yuzden nesne ve fiilin BIRLIKTE gecmesi aranir. Aksi halde
"barajda inceleme yapildi" gibi normal haberler de kesiciyi tetiklerdi.
"""

from __future__ import annotations

from itertools import count

from ..metin import icerir, normalize
from ..schemas import Iddia, IddiaTuru, Mesaj
from ..pipeline.triage import EYLEM_EMRI

TUR_SOZLUGU: dict[IddiaTuru, tuple[str, ...]] = {
    IddiaTuru.BARAJ: ("baraj", "golet", "gölet", "su yapisi", "su yapısı", "sedde"),
    IddiaTuru.SISMIK: ("artci", "artçı", "fay", "deprem buyuklugu", "deprem büyüklüğü", "tsunami"),
    IddiaTuru.FINANS: ("borsa", "bist", "dolar", "banka", "mevduat", "atm"),
    IddiaTuru.ELEKTRIK: ("elektrik", "trafo", "enerji nakil", "sebeke", "şebeke"),
    IddiaTuru.DOGALGAZ: ("dogalgaz", "doğalgaz", "gaz hatti", "gaz hattı", "botas", "botaş"),
    IddiaTuru.ULASIM: ("kopru", "köprü", "otoyol", "havalimani", "havalimanı", "viyaduk", "tunel"),
    IddiaTuru.HAVA: ("firtina", "fırtına", "sel", "kar", "hortum", "don"),
    IddiaTuru.SAGLIK: ("salgin", "salgın", "kolera", "hastane", "su zehirlenmesi", "epidemi"),
    IddiaTuru.ASAYIS: ("yagma", "yağma", "hirsizlik", "hırsızlık", "linc", "linç", "cete", "çete"),
}

IDDIA_FIIL = (
    "patladi", "patladı", "coktu", "çöktü", "yikildi", "yıkıldı", "kapandi",
    "kapandı", "kesildi", "tasti", "taştı", "bosaldi", "boşaldı", "sizinti",
    "sızıntı", "iflas", "durduruldu", "basladi", "başladı", "yayiliyor",
    "yayılıyor", "geliyor",
)


class IddiaTespitci:
    def __init__(self) -> None:
        self._sayac = count(1)

    def tur_belirle(self, metin: str) -> IddiaTuru:
        n = normalize(metin)
        for tur, sozcukler in TUR_SOZLUGU.items():
            if any(normalize(s) in n for s in sozcukler):
                return tur
        return IddiaTuru.BILINMIYOR

    def iddia_mi(self, metin: str) -> bool:
        """Nesne ve fiil birlikte geciyorsa sistemik iddiadir."""
        return (
            self.tur_belirle(metin) is not IddiaTuru.BILINMIYOR
            and icerir(metin, IDDIA_FIIL)
        )

    def __call__(self, mesaj: Mesaj) -> Iddia | None:
        if not self.iddia_mi(mesaj.metin):
            return None
        return Iddia(
            id=f"I-{next(self._sayac):05d}",
            mesaj=mesaj,
            tur=self.tur_belirle(mesaj.metin),
            eylem_tetikleyici=icerir(mesaj.metin, EYLEM_EMRI),
        )

"""Turkce metin yardimcilari.

Afet mesajlari karanlikta, panikle, cogu zaman Turkce klavye olmadan yazilir.
"kizim enkaz altinda" ile "kızım enkaz altında" ayni cumledir; sistemin ikisini
de ayni gormesi gerekir. Buradaki normalizasyon tum hatlarin girisinde calisir.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

# Turkce karakterlerin klavyesiz yazimda aldigi hal.
_KATLAMA = str.maketrans(
    {
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "I": "i", "İ": "i", "i": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
    }
)

_BOSLUK = re.compile(r"\s+")
_NOKTALAMA = re.compile(r"[^\w\s]", re.UNICODE)
_TEKRAR = re.compile(r"(.)\1{2,}")


def katla(s: str) -> str:
    """Turkce karakterleri ASCII karsiligina indirger, kucultur."""
    return unicodedata.normalize("NFC", s).translate(_KATLAMA).lower()


def normalize(s: str, noktalama_at: bool = True) -> str:
    """Karsilastirma icin kanonik hale getirir.

    Uzatmalari da kisaltir: "yardimmmm" -> "yardimm", boylece panik yazimi
    sozluk eslesmesini bozmaz.
    """
    s = katla(s)
    if noktalama_at:
        s = _NOKTALAMA.sub(" ", s)
    s = _TEKRAR.sub(r"\1\1", s)
    return _BOSLUK.sub(" ", s).strip()


def icerir(metin: str, sozcukler: tuple[str, ...]) -> bool:
    """Normalize edilmis metinde sozluk taramasi."""
    n = normalize(metin)
    return any(normalize(k) in n for k in sozcukler)


def kac_tane(metin: str, sozcukler: tuple[str, ...]) -> int:
    n = normalize(metin)
    return sum(1 for k in sozcukler if normalize(k) in n)


def benzerlik(a: str, b: str) -> float:
    """0-1 arasi metin benzerligi (normalize edilmis)."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def yakin_esles(aday: str, secenekler: list[str], esik: float = 0.82) -> str | None:
    """Yazim hatali mahalle/sokak adini sozlukteki dogru kayda baglar.

    "Armutalan" -> "Armutlu" gibi. Adres cikariminin en kirilgan yeri burasi;
    esigi dusurmek yanlis konumlandirmaya, yukseltmek kaydi kaybetmeye yol acar.
    """
    if not aday or not secenekler:
        return None
    hedef = normalize(aday)
    havuz = {normalize(s): s for s in secenekler}
    if hedef in havuz:
        return havuz[hedef]
    vurus = difflib.get_close_matches(hedef, list(havuz), n=1, cutoff=esik)
    return havuz[vurus[0]] if vurus else None


def sayi_bul(metin: str, kaliplar: tuple[str, ...]) -> int | None:
    """"3 kisiyiz", "4 kat" gibi kaliplardan sayiyi ceker."""
    n = normalize(metin)
    for kalip in kaliplar:
        m = re.search(rf"(\d+)\s*{kalip}", n)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None

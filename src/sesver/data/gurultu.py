"""Gercekci yazim bozulmasi.

Sablonlardan uretilmis temiz metin, afet akisini temsil etmez. Gercek
cagrilar karanlikta, tek elle, dusuk pille, panik halinde ve cogu zaman
Turkce klavye olmadan yazilir. Sablon ciktilarini oldugu gibi kullanmak
degerlendirmeyi yapay olarak kolaylastirir; bu modulun tek isi o kolayligi
kaldirmaktir.

Bozulma tipleri, 6 Subat 2023 sonrasi kamuya acik paylasimlarda gozlenen
yazim orunruntulerinden turetilmistir:

  - Turkce karakterlerin ASCII'ye dusmesi          "çöktü" -> "coktu"
  - Bitisik yazim ve bosluk kaybi                  "3. kat" -> "3.kat"
  - Harf dusmesi / komsu tusa basma                "enkaz" -> "enkz", "enkaa"
  - Sesli harf kaybi (hizli yazim)                 "yardim" -> "yardm"
  - Uzatma                                         "yardim" -> "yardiiiim"
  - Tamamen buyuk harf                             panik gostergesi
  - Noktalama kaybi ve tekrari
  - Mesajin yarida kesilmesi                       pil bitmesi / baglanti kopmasi
"""

from __future__ import annotations

import random

# Turkce Q klavyede komsu tuslar.
KOMSU = {
    "a": "sq", "e": "wr", "i": "uo", "o": "ip", "u": "yi",
    "n": "bm", "m": "n", "k": "jl", "l": "k", "r": "et",
    "t": "ry", "s": "ad", "d": "sf", "z": "x", "c": "vx",
}

SESLI = "aeiouıöü"


def _turkce_dusur(s: str) -> str:
    return s.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))


def _harf_dusur(s: str, rnd: random.Random) -> str:
    if len(s) < 4:
        return s
    i = rnd.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1:]


def _komsu_tus(s: str, rnd: random.Random) -> str:
    idx = [i for i, ch in enumerate(s) if ch.lower() in KOMSU]
    if not idx:
        return s
    i = rnd.choice(idx)
    return s[:i] + rnd.choice(KOMSU[s[i].lower()]) + s[i + 1:]


def _sesli_dusur(s: str, rnd: random.Random) -> str:
    idx = [i for i, ch in enumerate(s) if ch.lower() in SESLI and 0 < i < len(s) - 1]
    if not idx:
        return s
    i = rnd.choice(idx)
    return s[:i] + s[i + 1:]


def _uzat(s: str, rnd: random.Random) -> str:
    if not s:
        return s
    i = rnd.randrange(len(s))
    return s[:i] + s[i] * rnd.randint(2, 4) + s[i:]


def _bosluk_kaybi(s: str, rnd: random.Random) -> str:
    parcalar = s.split(" ")
    if len(parcalar) < 3:
        return s
    i = rnd.randrange(len(parcalar) - 1)
    return " ".join(parcalar[:i] + [parcalar[i] + parcalar[i + 1]] + parcalar[i + 2:])


def _kesil(s: str, rnd: random.Random) -> str:
    """Pil bitmesi veya baglanti kopmasi: mesaj yarida kalir."""
    if len(s) < 25:
        return s
    return s[: rnd.randint(len(s) // 2, len(s) - 5)].rstrip()


def boz(metin: str, rnd: random.Random, siddet: float = 1.0) -> str:
    """Metne gercekci yazim bozulmasi uygular.

    ``siddet`` 0 ise metin degismez, 1 ise tipik bir mobil yazim, 2 ise
    agir bozulma uretir.
    """
    if siddet <= 0:
        return metin
    s = metin

    if rnd.random() < 0.55 * siddet:
        s = _turkce_dusur(s)

    kelimeler = s.split(" ")
    for i, k in enumerate(kelimeler):
        if len(k) < 4 or rnd.random() > 0.18 * siddet:
            continue
        secim = rnd.random()
        if secim < 0.30:
            kelimeler[i] = _harf_dusur(k, rnd)
        elif secim < 0.55:
            kelimeler[i] = _komsu_tus(k, rnd)
        elif secim < 0.80:
            kelimeler[i] = _sesli_dusur(k, rnd)
        else:
            kelimeler[i] = _uzat(k, rnd)
    s = " ".join(kelimeler)

    if rnd.random() < 0.22 * siddet:
        s = _bosluk_kaybi(s, rnd)
    if rnd.random() < 0.16 * siddet:
        s = s.upper()
    if rnd.random() < 0.14 * siddet:
        s = s.replace(".", "") if rnd.random() < 0.5 else s + "!" * rnd.randint(1, 4)
    if rnd.random() < 0.07 * siddet:
        s = _kesil(s, rnd)

    return s.strip() or metin

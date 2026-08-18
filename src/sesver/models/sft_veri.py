"""DIVAN-COZ icin SFT egitim verisi uretimi: {mesaj, alanlar} ciftleri.

Etiketler, kural tabanli Cozumleyici'nin CIKTISI DEGIL, sentetik uretecin
kendi bildigi GERCEK degerlerdir (data/synth.py :: Olay). Aksi halde model,
gecmesi beklenen taban cizgisini taklit etmeye egitilirdi - bkz.
pipeline/extract.py docstring'i: Cozumleyici "DIVAN-COZ'a karsi durust bir
taban cizgisi"dir. Onu taklit eden bir model onu asamaz.

Sahte kampanya mesajlarinda mahalle, sozlukte olmayan uydurma bir isimdir
("Yilmazkent" gibi). Bu durumda alan yine de metindeki HALIYLE yazilir
(null degil): cikti semasi metin cikarimidir, dogruluk denetimi degil. O
denetim ayri bir asamadadir (pipeline/verify.py, data/gazetteer.py). Yalnizca
il/ilce -sozlukte cozulemeyen- null kalir.

Kosum::

    python -m sesver.models.sft_veri
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import CANLILIK_SOZCUKLER, KIRILGAN_SOZCUKLER
from ..data.gazetteer import Gazetteer, varsayilan_gazetteer
from ..data.synth import Akis, AkisUreteci, Olay
from ..metin import icerir

_KOK = Path(__file__).resolve().parents[3]
VARSAYILAN_EGITIM = _KOK / "data" / "sft_train.jsonl"
VARSAYILAN_DOGRULAMA = _KOK / "data" / "sft_val.jsonl"


def _alanlar(olay: Olay, metin: str, sahte: bool, g: Gazetteer) -> dict:
    if sahte:
        # Uydurma yer sozlukte cozulmez: il/ilce null, mahalle metindeki haliyle.
        il = ilce = None
        mahalle = f"{olay.bina}kent".title()
    else:
        vurus = g.mahalle_ara(olay.yer)
        if vurus:
            il, ilce, mahalle = vurus[0], vurus[1], vurus[2]
        else:
            il = ilce = None
            mahalle = olay.yer.title()

    return {
        "il": il,
        "ilce": ilce,
        "mahalle": mahalle,
        "sokak": f"{olay.sokak}. Sokak",
        "bina": olay.bina.title(),
        "kat": olay.kat,
        "kisi_sayisi": olay.kisi,
        "kirilgan": icerir(metin, KIRILGAN_SOZCUKLER),
        "ses_var": icerir(metin, CANLILIK_SOZCUKLER),
    }


def uret(mesaj_sayisi: int, seed: int) -> list[dict]:
    """Sentetik yardim cagrilarindan {mesaj, alanlar} SFT ornekleri uretir.

    Yalnizca CAGRI kalibiyla uretilmis mesajlar kullanilir (yanit zinciri,
    destek, gurultu, iddia haric) - DIVAN-COZ'un gorevi yalnizca cagri
    metninden alan cikarmaktir, siniflandirma degil.
    """
    akis: Akis = AkisUreteci(seed=seed).uret(mesaj_sayisi)
    g = varsayilan_gazetteer()
    ornekler: list[dict] = []
    for m in akis.mesajlar:
        oid = akis.mesaj_olay.get(m.id)
        if oid is None:
            continue
        olay = akis.olaylar[oid]
        sahte = m.id in akis.sahte_mesajlar
        ornekler.append({"mesaj": m.metin, "alanlar": _alanlar(olay, m.metin, sahte, g)})
    return ornekler


def dosyaya_yaz(ornekler: list[dict], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        for o in ornekler:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


def main() -> None:
    a = argparse.ArgumentParser(description="DIVAN-COZ SFT veri uretimi")
    a.add_argument("--egitim-mesaj", type=int, default=30_000)
    a.add_argument("--dogrulama-mesaj", type=int, default=6_000)
    a.add_argument("--egitim-seed", type=int, default=101)
    a.add_argument("--dogrulama-seed", type=int, default=202)
    a.add_argument("--egitim-cikti", type=Path, default=VARSAYILAN_EGITIM)
    a.add_argument("--dogrulama-cikti", type=Path, default=VARSAYILAN_DOGRULAMA)
    n = a.parse_args()

    egitim = uret(n.egitim_mesaj, n.egitim_seed)
    dogrulama = uret(n.dogrulama_mesaj, n.dogrulama_seed)
    dosyaya_yaz(egitim, n.egitim_cikti)
    dosyaya_yaz(dogrulama, n.dogrulama_cikti)
    print(f"  egitim:     {len(egitim):>6d} ornek -> {n.egitim_cikti}")
    print(f"  dogrulama:  {len(dogrulama):>6d} ornek -> {n.dogrulama_cikti}")


if __name__ == "__main__":
    main()

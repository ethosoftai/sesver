"""SFT egitim verisi ureteci: sentetik akis -> talimat/JSON ciftleri.

Egitim verisi neden sentetik uretiliyor, gerekcesi docs/veri-model-etik.md
icinde. Burasi o kararin uygulamasi: ureteci calistirir, her mesaj icin
YER GERCEGI olan alan sozlugunu yazar ve modeli bu esleme uzerinde egitiriz.

Cikti bicimi (jsonl):

    {"mesaj": "...", "alanlar": {"il": "Hatay", "ilce": "Antakya", ...}}

Kritik nokta: etiketler kural hattinin CIKTISI DEGIL, uretecin yer
gercegidir. Kural hattinin ciktisini etiket olarak kullansaydik model
yalnizca kural hattini taklit etmeyi ogrenirdi ve tavan oradan gelirdi.

Kosum:
    python -m sesver.models.veri_uret --egitim 40000 --dogrulama 4000
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from ..config import CANLILIK_SOZCUKLER, KIRILGAN_SOZCUKLER
from ..data.gazetteer import varsayilan_gazetteer
from ..data.synth import AkisUreteci
from ..metin import icerir, normalize

# Degerlendirme kumesi bu illerden secilir; egitimde kullanilmaz.
# Amac: model mahalle adi ezberleyerek degil, ADRES YAPISINI ogrenerek
# basarili olsun. Cografi ayriklik, asiri ogrenmeye karsi en guclu onlemdir.
DOGRULAMA_ILLERI = ("Adiyaman",)


def _alanlar(olay, mesaj_metni: str, g) -> dict:
    """Bir olayin yer gercegini model cikti semasina cevirir.

    KRITIK KURAL: metinde GECMEYEN alan etiketlenmez, None birakilir.

    Uretecin yer gercegi olayin tamamini bilir (kat, kisi sayisi, bina),
    ama her sablon bunlarin hepsini yazmaz. Yer gercegini oldugu gibi etiket
    yapmak, modele metinde olmayan bir bilgiyi uydurmayi ogretir - yani tam
    olarak bir afet sisteminde en tehlikeli davranisi. Bu yuzden her alan,
    normalize edilmis metinde gorunur olup olmadigina gore filtrelenir.
    """
    vurus = g.mahalle_ara(olay.yer)
    il = ilce = mahalle = None
    if vurus:
        il, ilce, mahalle = vurus[0], vurus[1], vurus[2]

    n = normalize(mesaj_metni)

    def gorunur_mahalle():
        return mahalle if mahalle and normalize(mahalle) in n else None

    def gorunur_sokak():
        for kalip in (f"{olay.sokak} sokak", f"{olay.sokak} sok",
                      f"{olay.sokak} cadde", f"{olay.sokak} cad"):
            if kalip in n:
                return f"{olay.sokak}. Sokak"
        return None

    def gorunur_bina():
        return olay.bina.title() if normalize(olay.bina) in n else None

    def gorunur_kat():
        return olay.kat if re.search(rf"\b{olay.kat}\s*kat", n) else None

    def gorunur_kisi():
        return olay.kisi if re.search(rf"\b{olay.kisi}\s*kisi", n) else None

    mah = gorunur_mahalle()
    return {
        # Il ve ilce mahalleden turetilir; mahalle gorunmuyorsa onlar da yok.
        "il": il if mah else None,
        "ilce": ilce if mah else None,
        "mahalle": mah,
        "sokak": gorunur_sokak(),
        "bina": gorunur_bina(),
        "kat": gorunur_kat(),
        "kisi_sayisi": gorunur_kisi(),
        "kirilgan": icerir(mesaj_metni, KIRILGAN_SOZCUKLER),
        "ses_var": icerir(mesaj_metni, CANLILIK_SOZCUKLER),
    }


def _bos_alanlar(mesaj_metni: str) -> dict:
    """Cagri olmayan mesajlar icin: model 'burada adres yok' demeyi ogrenmeli.

    Bu negatif ornekler olmadan model her mesajdan adres uydurur.
    """
    return {
        "il": None, "ilce": None, "mahalle": None, "sokak": None,
        "bina": None, "kat": None, "kisi_sayisi": None,
        "kirilgan": icerir(mesaj_metni, KIRILGAN_SOZCUKLER),
        "ses_var": icerir(mesaj_metni, CANLILIK_SOZCUKLER),
    }


def uret(mesaj_sayisi: int, seed: int, dogrulama: bool = False) -> list[dict]:
    g = varsayilan_gazetteer()
    akis = AkisUreteci(seed=seed).uret(mesaj_sayisi)
    idx = {m.id: m for m in akis.mesajlar}
    kayitlar: list[dict] = []

    for mid, oid in akis.mesaj_olay.items():
        olay = akis.olaylar[oid]
        mesaj = idx.get(mid)
        if mesaj is None or not olay.gercek:
            continue
        vurus = g.mahalle_ara(olay.yer)
        if not vurus:
            continue
        il = vurus[0]
        # Cografi ayriklik: dogrulama illeri egitime girmez, tersi de gecerli.
        if dogrulama != (il in DOGRULAMA_ILLERI):
            continue
        kayitlar.append({
            "mesaj": mesaj.metin,
            "alanlar": _alanlar(olay, mesaj.metin, g),
        })

    # Negatif ornekler: gurultu ve destek mesajlari, bos alan sozluguyle.
    negatif = [m for m in akis.mesajlar if m.id not in akis.mesaj_olay and not m.yanit_mi]
    rnd = random.Random(seed)
    rnd.shuffle(negatif)
    # Yaklasik %25 negatif oran: model her mesajda adres aramayi ogrenmemeli.
    hedef_negatif = max(1, len(kayitlar) // 3)
    for m in negatif[:hedef_negatif]:
        kayitlar.append({"mesaj": m.metin, "alanlar": _bos_alanlar(m.metin)})

    rnd.shuffle(kayitlar)
    return kayitlar


def yaz(kayitlar: list[dict], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


def main() -> None:
    a = argparse.ArgumentParser(description="SFT egitim verisi ureteci")
    a.add_argument("--egitim", type=int, default=40_000,
                   help="egitim akisindaki mesaj sayisi")
    a.add_argument("--dogrulama", type=int, default=8_000,
                   help="dogrulama akisindaki mesaj sayisi")
    a.add_argument("--cikti", default="data", help="cikti dizini")
    a.add_argument("--seed", type=int, default=42)
    n = a.parse_args()

    egitim = uret(n.egitim, seed=n.seed, dogrulama=False)
    dogrulama = uret(n.dogrulama, seed=n.seed + 1, dogrulama=True)

    d = Path(n.cikti)
    yaz(egitim, d / "sft_train.jsonl")
    yaz(dogrulama, d / "sft_val.jsonl")

    def sayim(kayitlar):
        adresli = sum(1 for k in kayitlar if k["alanlar"]["mahalle"])
        return adresli, len(kayitlar) - adresli

    e_a, e_b = sayim(egitim)
    d_a, d_b = sayim(dogrulama)
    print(f"egitim    : {len(egitim):>6} ornek  ({e_a} adresli, {e_b} negatif)")
    print(f"dogrulama : {len(dogrulama):>6} ornek  ({d_a} adresli, {d_b} negatif)")
    print(f"cografi ayriklik: dogrulama illeri = {DOGRULAMA_ILLERI}")
    print(f"yazildi: {d / 'sft_train.jsonl'}, {d / 'sft_val.jsonl'}")


if __name__ == "__main__":
    main()

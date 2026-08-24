"""DİVAN-AYIKLA egitimi, konformal kalibrasyonu ve durust degerlendirmesi.

    python -m sesver.models.egit_ayikla

Uc AYRI akis kullanilir; hicbiri digeriyle ortusmez:

    egitim      (seed A)  -> agirliklarin ogrenilmesi
    kalibrasyon (seed B)  -> konformal esigin belirlenmesi
    test        (seed C)  -> raporlanan tum sayilar

Kalibrasyon kumesinin egitimden ayri olmasi konformal garantinin on
kosuludur; test kumesinin her ikisinden de ayri olmasi ise sonuclarin
durustlugunun on kosuludur.

Cikti: checkpoints/divan-ayikla.json, checkpoints/divan-ayikla-konformal.json
       ve checkpoints/divan-ayikla-rapor.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..data.synth import AkisUreteci
from ..pipeline.triage import BirlesikTriyaj, KuralTriyaj
from ..schemas import Mesaj
from .ayikla import SINIFLAR, OrtalamaPerceptron
from .konformal import KonformalKapi


def ornekler(mesaj_sayisi: int, seed: int,
             sablon_yarisi: str | None = None) -> list[tuple[str, str]]:
    """Yanit olmayan her mesaj ve yer gercegi sinifi."""
    akis = AkisUreteci(seed=seed, sablon_yarisi=sablon_yarisi).uret(mesaj_sayisi)
    return [
        (m.metin, akis.mesaj_sinifi[m.id])
        for m in akis.mesajlar
        if not m.yanit_mi and m.id in akis.mesaj_sinifi
    ]


def _metrikler(gercek: list[str], tahmin: list[str]) -> dict:
    """Sinif bazli kesinlik/anma/F1 ve makro ortalama."""
    sonuc = {}
    for s in SINIFLAR:
        dp = sum(1 for g, t in zip(gercek, tahmin, strict=True) if g == s and t == s)
        yp = sum(1 for g, t in zip(gercek, tahmin, strict=True) if g != s and t == s)
        yn = sum(1 for g, t in zip(gercek, tahmin, strict=True) if g == s and t != s)
        kesinlik = dp / max(dp + yp, 1)
        anma = dp / max(dp + yn, 1)
        f1 = 2 * kesinlik * anma / max(kesinlik + anma, 1e-9)
        sonuc[s] = {"kesinlik": round(kesinlik, 4), "anma": round(anma, 4),
                    "f1": round(f1, 4), "destek": dp + yn}
    sonuc["makro_f1"] = round(
        sum(sonuc[s]["f1"] for s in SINIFLAR) / len(SINIFLAR), 4)
    sonuc["dogruluk"] = round(
        sum(1 for g, t in zip(gercek, tahmin, strict=True) if g == t) / max(len(gercek), 1), 4)
    # Afet baglaminda tek kritik sayi: kacirilan yardim cagrisi.
    sonuc["kacan_cagri"] = sum(
        1 for g, t in zip(gercek, tahmin, strict=True) if g == "cagri" and t != "cagri")
    return sonuc


def kural_tahminleri(veri: list[tuple[str, str]]) -> list[str]:
    kural = KuralTriyaj()
    from ..schemas import Hesap
    return [
        kural(Mesaj(id="x", metin=m, hesap=Hesap(id="h")))[0].value
        for m, _ in veri
    ]


def main() -> None:
    a = argparse.ArgumentParser(description="DİVAN-AYIKLA egitimi")
    a.add_argument("--egitim", type=int, default=30_000)
    a.add_argument("--kalibrasyon", type=int, default=12_000)
    a.add_argument("--test", type=int, default=12_000)
    a.add_argument("--epoch", type=int, default=8)
    a.add_argument("--alpha", type=float, default=0.05)
    a.add_argument("--cikti", default="checkpoints")
    n = a.parse_args()

    print("\n" + "=" * 68)
    print("  DİVAN-AYIKLA  ·  egitim ve konformal kalibrasyon")
    print("=" * 68)

    print("\n  [1/5] veri hazirlaniyor (uc ayri akis, SABLON AYRIK)")
    print("    egitim + kalibrasyon : 'a' sablon yarisi")
    print("    test                 : 'b' yarisi - modelin HIC GORMEDIGI ifadeler")
    egitim = ornekler(n.egitim, seed=101, sablon_yarisi="a")
    kalib = ornekler(n.kalibrasyon, seed=202, sablon_yarisi="a")
    test = ornekler(n.test, seed=303, sablon_yarisi="b")
    for ad, v in (("egitim", egitim), ("kalibrasyon", kalib), ("test", test)):
        dagilim = {s: sum(1 for _, e in v if e == s) for s in SINIFLAR}
        print(f"    {ad:12s} {len(v):>6} ornek   {dagilim}")

    print(f"\n  [2/5] egitim ({n.epoch} epoch, saf Python)")
    model = OrtalamaPerceptron()
    t0 = time.perf_counter()
    gecmis = model.egit(egitim, epoch=n.epoch)
    egitim_sn = time.perf_counter() - t0
    print(f"    sure {egitim_sn:.1f} sn  ·  {model.parametre_sayisi:,} "
          f"sifir olmayan agirlik".replace(",", "."))

    print("\n  [3/5] test kumesinde degerlendirme")
    t0 = time.perf_counter()
    model_ciktilari = [model.tahmin(m) for m, _ in test]
    cikarim_sn = time.perf_counter() - t0
    model_tahmin = [c[0] for c in model_ciktilari]
    olasiliklar = [c[2] for c in model_ciktilari]
    gercek = [e for _, e in test]

    m_metrik = _metrikler(gercek, model_tahmin)
    k_metrik = _metrikler(gercek, kural_tahminleri(test))

    # Asimetrik birlesim: CAGRI icin kural VEYA model, digerleri icin model.
    from ..schemas import Hesap
    from .ayikla import AyiklaModeli
    birlesik = BirlesikTriyaj(model=lambda msj: (
        __import__("sesver.schemas", fromlist=["Tur"]).Tur(
            AyiklaModeli(model).predict(msj.metin)[0]),
        AyiklaModeli(model).predict(msj.metin)[1]))
    b_tahmin = [
        birlesik(Mesaj(id="x", metin=m, hesap=Hesap(id="h")))[0].value
        for m, _ in test
    ]
    b_metrik = _metrikler(gercek, b_tahmin)

    print(f"    {'':22s} {'KURAL':>10s} {'MODEL':>10s} {'BIRLESIK':>10s}")
    for anahtar in ("dogruluk", "makro_f1"):
        print(f"    {anahtar:22s} {k_metrik[anahtar]:>10.4f} "
              f"{m_metrik[anahtar]:>10.4f} {b_metrik[anahtar]:>10.4f}")
    for s in SINIFLAR:
        print(f"    {'F1 (' + s + ')':22s} {k_metrik[s]['f1']:>10.4f} "
              f"{m_metrik[s]['f1']:>10.4f} {b_metrik[s]['f1']:>10.4f}")
    print(f"    {'KACAN CAGRI':22s} {k_metrik['kacan_cagri']:>10d} "
          f"{m_metrik['kacan_cagri']:>10d} {b_metrik['kacan_cagri']:>10d}"
          "     <- kritik")
    print(f"    cikarim hizi: {len(test) / cikarim_sn:,.0f} mesaj/sn"
          .replace(",", "."))

    print(f"\n  [4/5] konformal kalibrasyon (alpha={n.alpha})")
    kapi = KonformalKapi(alpha=n.alpha)
    kalib_olasilik = [model.tahmin(m)[2] for m, _ in kalib]
    kalib_gercek = [e for _, e in kalib]
    bilgi = kapi.kalibre(kalib_olasilik, kalib_gercek)
    print(f"    olasilik esigi {bilgi['olasilik_esigi']:.4f} "
          f"({bilgi['kalibrasyon_n']} ornek uzerinden)")

    kon = kapi.degerlendir(olasiliklar, gercek)
    print(f"    kapsama         {kon['kapsama']:.4f}  "
          f"(hedef >= {kon['hedef_kapsama']:.2f})  "
          f"{'GARANTI SAGLANDI' if kon['garanti_saglandi'] else 'IHLAL'}")
    print(f"    cekimserlik     {kon['cekimserlik']:.4f}  (insana devredilen)")
    print(f"    otomatik karar  {kon['otomatik_karar_orani']:.4f}  "
          f"dogruluk {kon['otomatik_kararda_dogruluk']:.4f}")

    egri = kapi.kapsama_risk_egrisi(kalib_olasilik, kalib_gercek)
    print("\n    kapsama-cekimserlik odunlesmesi:")
    print(f"      {'alpha':>6s} {'kapsama':>9s} {'cekimser':>9s} {'oto.dogruluk':>13s}")
    for e in egri:
        print(f"      {e['alpha']:>6.2f} {e['kapsama']:>9.4f} "
              f"{e['cekimserlik']:>9.4f} {e['otomatik_kararda_dogruluk']:>13.4f}")

    print("\n  [5/5] kaydediliyor")
    d = Path(n.cikti)
    model.kaydet(d / "divan-ayikla.json")
    kapi.kaydet(d / "divan-ayikla-konformal.json")
    rapor = {
        "egitim": {"ornek": len(egitim), "epoch": n.epoch,
                   "sure_sn": round(egitim_sn, 1),
                   "parametre": model.parametre_sayisi, "gecmis": gecmis},
        "test": {"ornek": len(test), "model": m_metrik, "kural": k_metrik,
                 "birlesik": b_metrik,
                 "cikarim_mesaj_sn": round(len(test) / cikarim_sn)},
        "konformal": {"kalibrasyon": bilgi, "test": kon, "egri": egri},
    }
    with open(d / "divan-ayikla-rapor.json", "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    boyut = (d / "divan-ayikla.json").stat().st_size / 1024
    print(f"    {d / 'divan-ayikla.json'}  ({boyut:.0f} KB)")
    print(f"    {d / 'divan-ayikla-konformal.json'}")
    print(f"    {d / 'divan-ayikla-rapor.json'}")
    print("\n" + "=" * 68 + "\n")


if __name__ == "__main__":
    main()

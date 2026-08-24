"""Konformal kalibrasyon — garantili hata butcesiyle cekimserlik.

Problem
-------
Bir siniflandiricinin "%92 eminim" demesi hicbir sey garanti etmez; softmax
ciktilari kalibre degildir ve dagilim kaydiginda once bu skorlar bozulur.
Afet baglaminda "model emin sanmisti ama yanildi" kabul edilebilir bir hata
kipi degildir.

Cozum: bolunmus konformal tahmin (split conformal prediction)
--------------------------------------------------------------
Modelin ic skorlarina hic guvenmeyiz. Bunun yerine, egitimde KULLANILMAYAN
bir kalibrasyon kumesi uzerinde modelin gercek hata dagilimini olceriz.

  1. Kalibrasyon kumesindeki her ornek icin uygunsuzluk skoru:
         s_i = 1 - p(gercek sinif | x_i)
     Model gercek sinifa ne kadar dusuk olasilik verdiyse skor o kadar yuksek.

  2. Bu skorlarin (1-alpha) ampirik yuzdeligi alinir:
         q = ceil((n+1)(1-alpha)) / n  yuzdeligi

  3. Yeni bir ornek icin TAHMIN KUMESI:
         C(x) = { y : p(y|x) >= 1 - q }

Degisim kabiliyeti (exchangeability) varsayimi altinda su GARANTI saglanir:

         P( gercek sinif ∈ C(x) )  >=  1 - alpha

Bu, modelin kendi ozguvenine degil, olculmus hata dagilimina dayanan bir
garantidir ve dagitimdan bagimsizdir (distribution-free).

Karar kurali
------------
  |C(x)| == 1  ->  tekil ve guvenli karar, otomatik islenir
  |C(x)| >  1  ->  model iki sinif arasinda kararsiz, INSANA DEVREDILIR
  |C(x)| == 0  ->  hicbir sinif esigi gecmiyor; ornek dagilimin disinda,
                   yine INSANA DEVREDILIR

Bu, projenin "kayit silinmez, siralanir" ilkesinin model duzeyindeki
karsiligidir: model emin degilse karar vermez, kuyruga koyar.

Olculecek iki sayi
------------------
  KAPSAMA  : gercek sinifin tahmin kumesinde bulunma orani (>= 1-alpha olmali)
  CEKIMSER : insana devredilen ornek orani (insan is yukunun maliyeti)

Aralarinda dogrudan bir odunlesme vardir; alpha bu odunlesmenin kontrol
dugmesidir ve onceden ILAN EDILIR.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KonformalKapi:
    """Bolunmus konformal tahmin kapisi.

    Args:
        alpha: kabul edilen hata butcesi. 0.05 -> en az %95 kapsama garantisi.
    """

    alpha: float = 0.05
    esik: float = 0.0                  # 1 - q  (kalibrasyondan gelir)
    kalibrasyon_n: int = 0
    skorlar: list[float] = field(default_factory=list)

    # --- kalibrasyon ---

    def kalibre(self, olasiliklar: list[dict[str, float]],
                gercekler: list[str]) -> dict:
        """Kalibrasyon kumesi uzerinde esigi belirler.

        Bu kume egitimde KULLANILMAMIS olmalidir; aksi halde garanti gecersizdir.
        """
        if len(olasiliklar) != len(gercekler):
            raise ValueError("olasilik ve etiket sayilari esit olmali")
        n = len(gercekler)
        if n < 20:
            raise ValueError("kalibrasyon icin en az 20 ornek gerekir")

        # Uygunsuzluk skoru: gercek sinifa verilen olasiligin tumleyeni.
        self.skorlar = sorted(1.0 - o.get(g, 0.0) for o, g in zip(olasiliklar, gercekler, strict=True))
        self.kalibrasyon_n = n

        # Sonlu ornek duzeltmeli yuzdelik: ceil((n+1)(1-alpha)) / n
        # alpha cok kucukse hicbir esik garanti veremez; en muhafazakar
        # deger olan 1.0 secilir (tahmin kumesi tum siniflari icerir).
        sira = math.ceil((n + 1) * (1 - self.alpha))
        q = 1.0 if sira > n else self.skorlar[sira - 1]
        self.esik = 1.0 - q
        return {
            "alpha": self.alpha,
            "kalibrasyon_n": n,
            "uygunsuzluk_yuzdeligi_q": round(q, 4),
            "olasilik_esigi": round(self.esik, 4),
        }

    # --- karar ---

    def tahmin_kumesi(self, olasilik: dict[str, float]) -> set[str]:
        return {s for s, p in olasilik.items() if p >= self.esik}

    def cekimser(self, olasilik: dict[str, float]) -> bool:
        """Tekil olmayan her tahmin kumesi insana devredilir."""
        return len(self.tahmin_kumesi(olasilik)) != 1

    # --- degerlendirme ---

    def degerlendir(self, olasiliklar: list[dict[str, float]],
                    gercekler: list[str]) -> dict:
        """Ayri bir test kumesinde kapsama ve cekimserligi olcer."""
        kapsanan = tekil = cekimser = bos = 0
        tekil_dogru = 0
        for o, g in zip(olasiliklar, gercekler, strict=True):
            kume = self.tahmin_kumesi(o)
            if g in kume:
                kapsanan += 1
            if len(kume) == 1:
                tekil += 1
                if next(iter(kume)) == g:
                    tekil_dogru += 1
            elif len(kume) == 0:
                bos += 1
                cekimser += 1
            else:
                cekimser += 1
        n = max(len(gercekler), 1)
        return {
            "n": len(gercekler),
            "kapsama": round(kapsanan / n, 4),
            "hedef_kapsama": round(1 - self.alpha, 4),
            "garanti_saglandi": (kapsanan / n) >= (1 - self.alpha) - 0.02,
            "cekimserlik": round(cekimser / n, 4),
            "bos_kume": bos,
            "otomatik_karar_orani": round(tekil / n, 4),
            "otomatik_kararda_dogruluk": round(tekil_dogru / max(tekil, 1), 4),
        }

    def kapsama_risk_egrisi(self, olasiliklar, gercekler,
                            alfalar=(0.01, 0.02, 0.05, 0.10, 0.20)) -> list[dict]:
        """Farkli hata butceleri icin kapsama-cekimserlik odunlesmesi.

        Raporda tek bir nokta degil, egrinin tamami sunulur: hangi insan
        is yukuyle hangi garantinin alindigi acikca gorulur.
        """
        egri = []
        asil = self.alpha
        for a in alfalar:
            self.alpha = a
            self.kalibre(olasiliklar[: len(olasiliklar) // 2],
                         gercekler[: len(gercekler) // 2])
            sonuc = self.degerlendir(olasiliklar[len(olasiliklar) // 2:],
                                     gercekler[len(gercekler) // 2:])
            egri.append({"alpha": a, **sonuc})
        self.alpha = asil
        return egri

    # --- kalicilik ---

    def kaydet(self, yol: str | Path) -> None:
        yol = Path(yol)
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({"alpha": self.alpha, "esik": self.esik,
                       "kalibrasyon_n": self.kalibrasyon_n}, f)

    @classmethod
    def yukle(cls, yol: str | Path) -> KonformalKapi:
        with open(yol, encoding="utf-8") as f:
            h = json.load(f)
        return cls(alpha=h["alpha"], esik=h["esik"],
                   kalibrasyon_n=h["kalibrasyon_n"])

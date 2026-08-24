"""DİVAN-AYIKLA — triyaj icin egitilmis siniflandirici.

Neden buyuk bir dil modeli degil?
---------------------------------
Triyaj, akistaki HER mesaja uygulanir. Bir afette bu saniyede on binlerce
cagri demektir ve karar butcesi milisaniyelerdir. Bu asamada bir uretici
model kullanmak, hem gecikme hem maliyet acisindan savunulamaz. Kaskadin
dogru tasarimi sudur: ucuz ve hizli bir siniflandirici her mesaja, pahali
model yalnizca gri bolgeye.

Neden harici kutuphane yok?
---------------------------
Afette ilk kesilen sey ag baglantisidir; ikinci kesilen sey kurulum
yapabilme imkanidir. Bu model saf Python ile egitilir ve kosar: ne numpy,
ne scikit-learn, ne PyTorch. Egitilmis agirliklar tek bir JSON dosyasidir,
bir USB bellekten kopyalanip calistirilabilir.

Yontem
------
Karakter n-gram karma (hashing) ozellikleri uzerinde ORTALAMALI PERCEPTRON.

Karakter n-gramlari Turkce icin bilincli bir secimdir: afet mesajlari
Turkce klavye olmadan, yazim hatalariyla ve eklerle yazilir. "enkazdayiz",
"enkaz altindayiz", "enkzda kaldik" kelime duzeyinde uc ayri belirtecken,
karakter duzeyinde ayni cekirdegi paylasir.

Ortalama alma, perceptron'un son orneklere asiri tepki verme egilimini
kirar ve tek gecisli egitimde bile kararli genelleme saglar.
"""

from __future__ import annotations

import json
import math
import random
import zlib
from pathlib import Path

SINIFLAR = ("cagri", "iddia", "destek", "gurultu")

# Karma alani. 2^18 = 262.144 kova; egitim kumemiz icin fazlasiyla yeterli,
# agirlik dosyasi seyrek tutuldugu icin boyut sorun degil.
KOVA = 1 << 18


def _karma(parca: str) -> int:
    """Surecler arasi KARARLI karma.

    Python'un yerlesik hash() fonksiyonu metinler icin her sureçte farkli
    tohum kullanir; egitilen model baska bir sureçte yuklendiginde ozellik
    indisleri kayardi. crc32 kararlidir.
    """
    return zlib.crc32(parca.encode("utf-8")) % KOVA


def ozellikler(metin: str) -> dict[int, float]:
    """Metni seyrek, L2-normalize edilmis ozellik vektorune cevirir."""
    from ..metin import normalize

    n = normalize(metin)
    sayim: dict[int, float] = {}

    def ekle(parca: str, agirlik: float = 1.0) -> None:
        i = _karma(parca)
        sayim[i] = sayim.get(i, 0.0) + agirlik

    # Karakter n-gramlari (3-5): yazim hatasi ve ek toleransini bunlar saglar.
    dolgulu = f" {n} "
    for boy in (3, 4, 5):
        for i in range(len(dolgulu) - boy + 1):
            ekle(f"k{boy}:{dolgulu[i:i + boy]}")

    # Kelime birimleri ve ikilileri: "ses geliyor", "yardim edebilirim" gibi
    # ayirt edici obekler karakter duzeyinde seyreliyor.
    kelimeler = n.split()
    for k in kelimeler:
        ekle(f"w:{k}", 1.5)
    for a, b in zip(kelimeler, kelimeler[1:], strict=False):
        ekle(f"w2:{a}_{b}", 1.5)

    # Yapisal ipuclari: adres kaliplari ve sayilar sinifi guclu belirler.
    if any(ch.isdigit() for ch in n):
        ekle("y:sayi_var", 2.0)
    for isaret in ("mah", "sokak", "sok", "apartmani", "apt", "kat", "site"):
        if f" {isaret} " in dolgulu:
            ekle(f"y:adres_{isaret}", 2.0)
    ekle("y:onyargi", 1.0)  # sabit terim

    norm = math.sqrt(sum(v * v for v in sayim.values())) or 1.0
    return {i: v / norm for i, v in sayim.items()}


class OrtalamaPerceptron:
    """Cok siniflı ortalamali perceptron."""

    def __init__(self, siniflar: tuple[str, ...] = SINIFLAR) -> None:
        self.siniflar = tuple(siniflar)
        self.w: dict[str, dict[int, float]] = {s: {} for s in self.siniflar}
        self._u: dict[str, dict[int, float]] = {s: {} for s in self.siniflar}
        self._t = 1
        self.egitildi = False

    # --- puanlama ---

    def _skorlar(self, x: dict[int, float]) -> dict[str, float]:
        return {
            s: sum(v * self.w[s].get(i, 0.0) for i, v in x.items())
            for s in self.siniflar
        }

    def tahmin(self, metin: str) -> tuple[str, float, dict[str, float]]:
        """(sinif, guven, olasiliklar) doner."""
        x = ozellikler(metin)
        skor = self._skorlar(x)
        olasilik = self._softmax(skor)
        sinif = max(olasilik, key=lambda s: olasilik[s])
        return sinif, olasilik[sinif], olasilik

    @staticmethod
    def _softmax(skor: dict[str, float], sicaklik: float = 1.0) -> dict[str, float]:
        enb = max(skor.values())
        us = {s: math.exp((v - enb) / sicaklik) for s, v in skor.items()}
        toplam = sum(us.values()) or 1.0
        return {s: v / toplam for s, v in us.items()}

    # --- egitim ---

    def egit(self, ornekler: list[tuple[str, str]], epoch: int = 8,
             seed: int = 42, sessiz: bool = False) -> list[dict]:
        """ornekler: [(metin, sinif), ...]"""
        rnd = random.Random(seed)
        veri = [(ozellikler(m), s) for m, s in ornekler]
        gecmis: list[dict] = []

        for e in range(1, epoch + 1):
            rnd.shuffle(veri)
            hata = 0
            for x, altin in veri:
                skor = self._skorlar(x)
                tahmin = max(skor, key=lambda s: skor[s])
                if tahmin != altin:
                    hata += 1
                    for i, v in x.items():
                        self.w[altin][i] = self.w[altin].get(i, 0.0) + v
                        self.w[tahmin][i] = self.w[tahmin].get(i, 0.0) - v
                        self._u[altin][i] = self._u[altin].get(i, 0.0) + self._t * v
                        self._u[tahmin][i] = self._u[tahmin].get(i, 0.0) - self._t * v
                self._t += 1
            oran = 1 - hata / max(len(veri), 1)
            gecmis.append({"epoch": e, "egitim_dogrulugu": round(oran, 4),
                           "hata": hata})
            if not sessiz:
                print(f"    epoch {e}/{epoch}  egitim dogrulugu {oran:.4f}  "
                      f"({hata} hata)")
        self._ortala()
        self.egitildi = True
        return gecmis

    def _ortala(self) -> None:
        """Agirliklari zamana gore ortalar - genellemenin asil kaynagi."""
        for s in self.siniflar:
            for i, u in self._u[s].items():
                self.w[s][i] = self.w[s].get(i, 0.0) - u / self._t
            # Seyrekligi koru: sifira cok yakin agirliklari at.
            self.w[s] = {i: v for i, v in self.w[s].items() if abs(v) > 1e-7}

    # --- kalicilik ---

    def kaydet(self, yol: str | Path) -> None:
        yol = Path(yol)
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "siniflar": list(self.siniflar),
                "kova": KOVA,
                "agirlik": {s: {str(i): round(v, 6) for i, v in self.w[s].items()}
                            for s in self.siniflar},
            }, f)

    @classmethod
    def yukle(cls, yol: str | Path) -> OrtalamaPerceptron:
        with open(yol, encoding="utf-8") as f:
            ham = json.load(f)
        m = cls(tuple(ham["siniflar"]))
        m.w = {s: {int(i): v for i, v in ham["agirlik"][s].items()}
               for s in m.siniflar}
        m.egitildi = True
        return m

    @property
    def parametre_sayisi(self) -> int:
        return sum(len(self.w[s]) for s in self.siniflar)


# Boru hattinin bekledigi arayuz: predict(metin) -> (etiket, guven)
class AyiklaModeli:
    """``pipeline.triage.ModelTriyaj`` sarmalayicisinin bekledigi arayuz."""

    def __init__(self, model: OrtalamaPerceptron, kapi=None) -> None:
        self.model = model
        self.kapi = kapi   # opsiyonel konformal kapi

    def predict(self, metin: str) -> tuple[str, float]:
        sinif, guven, olasilik = self.model.tahmin(metin)
        if self.kapi is not None and self.kapi.cekimser(olasilik):
            # Belirsiz: kacirmak elemekten kotudur, cagri lehine duselim.
            return "cagri", guven
        return sinif, guven


def varsayilan_model_yolu() -> Path:
    return Path(__file__).resolve().parents[3] / "checkpoints" / "divan-ayikla.json"

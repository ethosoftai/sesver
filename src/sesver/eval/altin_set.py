"""Bagimsiz altin set: sentetik degil, gercek bir afetten elle etiketlenmis
veriye karsi dogrulama.

Kaynak: Toraman ve ark. (2023), "Tweets Under the Rubble: Detection of
Messages Calling for Help in Earthquake Disaster" - 6 Subat 2023 depreminde
1000 Turkce tweet, elle etiketlenmis (yardim cagrisi var/yok). Bkz.
`data/kaynaklar/ATIF.md` (kaynak, lisans, atif) ve `docs/veri-model-etik.md`
bolum 1.1 ("altin set depoda yayinlanmaz, yalnizca metrikleri raporlanir").

IKI ADIMLI CALISIR
-------------------
1. KAYNAK_YUKLE - yalnizca tweet_id + etiket + varlik ofseti okunur. Ham
   metin YOK; kaynak depo da metni gizlilik/Twitter-X kullanim sartlari
   geregi dagitmiyor, tipki bu projenin kendi ilkesiyle tutarli sekilde.
2. HIDRAT (opsiyonel) - X API v2 ile tweet_id -> metin cozulur. Bunun icin
   ``SESVER_X_BEARER_TOKEN`` gerekir. Hidrat edilmis metin ``data/gold/``
   altina onbelleklenir ve ASLA commit edilmez (bkz. .gitignore).

Token yoksa yalnizca etiket dagilimi raporlanir; metin gerektiren triyaj
metrigi atlanir. Hat bu durumda da susmaz (fail-open).

ONEMLI KISIT
------------
Kaynak veri setindeki "yardim cagrisi" etiketi kurtarma + malzeme + bagis
taleplerini kapsar; bu projenin ``Tur.CAGRI`` tanimindan (afetzedenin kendi
kurtarilma cagrisi) biraz daha genistir. Bu yuzden buradaki anma/kesinlik
bir YAKLASIK sinir olarak okunmalidir, birebir ayni tanim degildir.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..pipeline.triage import KuralTriyaj
from ..schemas import Hesap, Mesaj, Tur

_KOK = Path(__file__).resolve().parents[3]
KAYNAK_TSV = _KOK / "data" / "kaynaklar" / "avaapm_deprem_id_etiket.tsv"
HIDRAT_CACHE = _KOK / "data" / "gold" / "avaapm_deprem_hidrat.jsonl"

X_API_URL = "https://api.twitter.com/2/tweets"


@dataclass(slots=True)
class AltinKayit:
    tweet_id: str
    yardim_cagrisi: bool
    varlik_sayisi: int
    metin: str | None = None


def kaynak_yukle(yol: Path = KAYNAK_TSV) -> list[AltinKayit]:
    kayitlar: list[AltinKayit] = []
    with open(yol, encoding="utf-8") as f:
        basliklar = next(f).rstrip("\n").split("\t")
        for satir in f:
            satir = satir.rstrip("\n")
            if not satir:
                continue
            alanlar = satir.split("\t")
            veri = dict(zip(basliklar, alanlar, strict=False))
            varliklar = veri.get("entities", "").strip()
            kayitlar.append(
                AltinKayit(
                    tweet_id=veri["tweet_id"],
                    yardim_cagrisi=veri["label"] == "1",
                    varlik_sayisi=len(varliklar.split("|")) if varliklar else 0,
                )
            )
    return kayitlar


def hidrat_cache_yukle(yol: Path = HIDRAT_CACHE) -> dict[str, str]:
    if not yol.exists():
        return {}
    onbellek: dict[str, str] = {}
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                obj = json.loads(satir)
                onbellek[obj["tweet_id"]] = obj["metin"]
    return onbellek


def hidrat(
    kayitlar: list[AltinKayit],
    bearer_token: str | None = None,
    cache_yolu: Path = HIDRAT_CACHE,
) -> int:
    """X API v2 ile eksik metinleri coker. Onbellegi once kullanir.

    Doner: bu cagrida yeni hidrat edilen kayit sayisi. Token yoksa ya da
    ag hatasi olursa 0 doner, hat durmaz (fail-open).
    """
    bearer_token = bearer_token or os.environ.get("SESVER_X_BEARER_TOKEN")
    onbellek = hidrat_cache_yukle(cache_yolu)
    for k in kayitlar:
        if k.tweet_id in onbellek:
            k.metin = onbellek[k.tweet_id]

    eksikler = [k for k in kayitlar if k.metin is None]
    if not eksikler or not bearer_token:
        return 0

    yeni = 0
    cache_yolu.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_yolu, "a", encoding="utf-8") as f:
        for i in range(0, len(eksikler), 100):
            grup = eksikler[i : i + 100]
            ids = ",".join(k.tweet_id for k in grup)
            istek = urllib.request.Request(
                f"{X_API_URL}?ids={ids}",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            try:
                with urllib.request.urlopen(istek, timeout=15) as yanit:
                    veri = json.loads(yanit.read())
            except (urllib.error.URLError, TimeoutError):
                continue  # fail-open: cozulmeyen grup atlanir, akis devam eder

            grup_map = {k.tweet_id: k for k in grup}
            for obj in veri.get("data", []):
                metin, tid = obj["text"], obj["id"]
                if tid in grup_map:
                    grup_map[tid].metin = metin
                f.write(json.dumps({"tweet_id": tid, "metin": metin}, ensure_ascii=False) + "\n")
                yeni += 1
            if i + 100 < len(eksikler):
                time.sleep(1)  # kaba rate-limit nezaketi
    return yeni


@dataclass(slots=True)
class AltinRapor:
    toplam: int
    hidrat_edilen: int
    etiket_dagilimi: dict[str, int] = field(default_factory=dict)
    anma: float | None = None
    kesinlik: float | None = None
    f1: float | None = None
    kacan: int | None = None

    def yazdir(self) -> str:
        satir = [
            "",
            "=" * 66,
            "  BAGIMSIZ ALTIN SET (Toraman ve ark. 2023, gercek deprem verisi)",
            "=" * 66,
            "",
            f"  toplam kayit         {self.toplam}",
            f"  hidrat edilen        {self.hidrat_edilen} / {self.toplam}",
            f"  yardim cagrisi (+)   {self.etiket_dagilimi.get('cagri', 0)}",
            f"  yardim cagrisi (-)   {self.etiket_dagilimi.get('cagri_degil', 0)}",
            "",
        ]
        if self.anma is None:
            satir += [
                "  metin hidrat edilmedi (SESVER_X_BEARER_TOKEN yok).",
                "  yalnizca etiket dagilimi raporlanabildi; triyaj metrigi",
                "  hesaplanamadi.",
                "",
            ]
        else:
            satir += [
                "  KURAL HATTI TRIYAJ (bagimsiz, gercek veri uzerinde)",
                f"    anma            {self.anma:.4f}",
                f"    kesinlik        {self.kesinlik:.4f}",
                f"    F1              {self.f1:.4f}",
                f"    kacan cagri     {self.kacan}",
                "",
                "  not: kaynak etiketi kurtarma+malzeme+bagis talebini kapsar,",
                "  Tur.CAGRI'dan biraz daha genistir - yaklasik sinir olarak oku.",
                "",
            ]
        satir += ["=" * 66, ""]
        return "\n".join(satir)


def degerlendir(kayitlar: list[AltinKayit]) -> AltinRapor:
    dagilim = {
        "cagri": sum(1 for k in kayitlar if k.yardim_cagrisi),
        "cagri_degil": sum(1 for k in kayitlar if not k.yardim_cagrisi),
    }
    hidrat_edilen = sum(1 for k in kayitlar if k.metin is not None)
    hidratli = [k for k in kayitlar if k.metin]

    if not hidratli:
        return AltinRapor(len(kayitlar), hidrat_edilen, dagilim)

    triyaj = KuralTriyaj()
    dp = yn = yp = 0
    for k in hidratli:
        mesaj = Mesaj(id=k.tweet_id, metin=k.metin or "", hesap=Hesap(id=f"altin-{k.tweet_id}"))
        tahmin, _ = triyaj(mesaj)
        tahmin_cagri = tahmin is Tur.CAGRI
        if k.yardim_cagrisi and tahmin_cagri:
            dp += 1
        elif k.yardim_cagrisi:
            yn += 1
        elif tahmin_cagri:
            yp += 1

    anma = dp / max(dp + yn, 1)
    kesinlik = dp / max(dp + yp, 1)
    f1 = 2 * anma * kesinlik / max(anma + kesinlik, 1e-9)
    return AltinRapor(
        toplam=len(kayitlar),
        hidrat_edilen=hidrat_edilen,
        etiket_dagilimi=dagilim,
        anma=round(anma, 4),
        kesinlik=round(kesinlik, 4),
        f1=round(f1, 4),
        kacan=yn,
    )


def kosum(bearer_token: str | None = None) -> AltinRapor:
    """Tek cagrida: kaynagi yukle, mumkunse hidrat et, degerlendir."""
    kayitlar = kaynak_yukle()
    hidrat(kayitlar, bearer_token=bearer_token)
    return degerlendir(kayitlar)

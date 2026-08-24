"""Standart kutuphane HTTP sunucusu.

Kurulum gerektirmez, internet gerektirmez. Koordinasyon merkezindeki
dizustunde tek komutla kalkar:

    python -m sesver.cli panel

Uc numaralandirilmis uc nokta grubu vardir: akis girisi, gorev kuyrugu ve
kamuya acik gorunumler. Her ucu de ayni ``BoruHatti`` ornegini paylasir.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..data.synth import AkisUreteci
from ..pipeline.graph import BoruHatti
from ..schemas import Alici, Durum, Hesap, Mesaj


class Oturum:
    """Paylasilan boru hatti durumu. Tum istekler ayni ornek uzerinde calisir."""

    def __init__(self) -> None:
        self.kilit = threading.Lock()
        self.sifirla()

    def sifirla(self) -> None:
        self.hat = BoruHatti()
        self.ureteci = AkisUreteci(seed=int(time.time()) % 10_000)
        self.sayac = 0
        self.baslangic = time.time()

    # --- akis girisi ---

    def demo_besle(self, adet: int) -> dict:
        """Sentetik akistan N mesaj isler. Canli demo icin."""
        akis = self.ureteci.uret(adet)
        t0 = time.perf_counter()
        with self.kilit:
            for m in akis.mesajlar:
                self.hat.isle(m)
            self.hat.kuyruk()
        sn = time.perf_counter() - t0
        return {
            "islenen": len(akis.mesajlar),
            "sure_sn": round(sn, 3),
            "mesaj_sn": round(len(akis.mesajlar) / max(sn, 1e-9)),
        }

    def cagri_ekle(self, veri: dict) -> dict:
        """Yapilandirilmis yardim cagrisi bestecisinden gelen kayit.

        Bu kanal serbest metne gore ayricaliklidir: konum cihazdan geldigi
        icin adres cikariminin en kirilgan adimi tamamen atlanir.
        """
        self.sayac += 1
        parcalar = [veri.get("metin", "").strip()]
        if veri.get("kisi"):
            parcalar.append(f"{veri['kisi']} kisiyiz")
        if veri.get("kat") not in (None, ""):
            parcalar.append(f"{veri['kat']}. kat")
        if veri.get("kirilgan"):
            parcalar.append("cocuk var")
        if veri.get("ses"):
            parcalar.append("ses geliyor")
        metin = " ".join(p for p in parcalar if p) or "enkaz altindayiz yardim edin"

        konum = None
        if veri.get("lat") is not None and veri.get("lon") is not None:
            konum = (float(veri["lat"]), float(veri["lon"]))

        mesaj = Mesaj(
            id=f"U-{self.sayac:06d}",
            metin=metin,
            hesap=Hesap(id=veri.get("hesap", f"kullanici{self.sayac}"),
                        yas_gun=900, bolgede_gecmis=True),
            ts=time.time(),
            konum_etiketi=konum,
        )
        with self.kilit:
            self.hat.isle(mesaj)
            kuyruk = self.hat.kuyruk()
        for g in kuyruk:
            if any(c.mesaj.id == mesaj.id for c in g.cagrilar):
                return {"gorev_id": g.id, "durum": g.durum.value,
                        "guven": g.guven, "oncelik": g.oncelik}
        return {"gorev_id": None, "durum": "konumsuz",
                "not": "Adres cozulemedi, gonullu zenginlestirme havuzuna alindi."}

    # --- gorunumler ---

    def ozet(self) -> dict:
        with self.kilit:
            o = self.hat.ozet()
            kuyruk = self.hat.kuyruk()
        dagilim: dict[str, int] = {}
        for g in kuyruk:
            dagilim[g.durum.value] = dagilim.get(g.durum.value, 0) + 1
        return {
            **{k: v for k, v in o.items() if k != "asama_sn"},
            "durum_dagilimi": dagilim,
            "konumsuz_havuz": len(self.hat.birlestirici.konumsuz),
            "calisma_sn": round(time.time() - self.baslangic),
        }

    def kuyruk(self, limit: int = 50) -> list[dict]:
        with self.kilit:
            gorevler = self.hat.kuyruk()[:limit]
        return [self._gorev_ozet(g) for g in gorevler]

    @staticmethod
    def _gorev_ozet(g) -> dict:
        k = g.konum
        return {
            "id": g.id,
            "oncelik": round(g.oncelik, 4),
            "guven": round(g.guven, 3),
            "durum": g.durum.value,
            "il": k.il, "ilce": k.ilce, "mahalle": k.mahalle,
            "sokak": k.sokak, "bina": k.bina, "kat": k.kat,
            "cozunurluk": k.cozunurluk.value,
            "bagimsiz_kaynak": g.bagimsiz_kaynak,
            "kopya": g.kopya_sayisi,
            "celiski": g.celiski,
            "kisi_sayisi": max((c.kisi_sayisi or 0) for c in g.cagrilar) or None,
            "kirilgan": any(c.kirilgan for c in g.cagrilar),
            "ses_var": any(c.ses_var for c in g.cagrilar),
            "yas_dk": round(g.yas_dk(), 1),
        }

    def gorev(self, gorev_id: str) -> dict | None:
        """Kanit karti: karar izleri ve kaynak metinler."""
        with self.kilit:
            g = self.hat.birlestirici.gorevler.get(gorev_id)
            if g is None:
                return None
            sevkler = self.hat.yonlendirici.gorev_sevkleri(g)
            ozet = self._gorev_ozet(g)
            ozet["iz"] = list(g.iz)
            ozet["kaynaklar"] = [
                {"hesap": c.mesaj.hesap.id,
                 "yeni_hesap": c.mesaj.hesap.yeni_hesap,
                 "bolgede_gecmis": c.mesaj.hesap.bolgede_gecmis,
                 "metin": c.aciklama}
                for c in g.cagrilar[:8]
            ]
            ozet["sevkler"] = [
                {"alici": s.alici.value, "konu": s.konu, "gerekce": s.gerekce,
                 "alanlar": sorted(s.yuk)}
                for s in sevkler
            ]
        return ozet

    def kapat(self, gorev_id: str, kim: str) -> dict:
        with self.kilit:
            g = self.hat.birlestirici.gorevler.get(gorev_id)
            if g is None:
                return {"hata": "gorev bulunamadi"}
            self.hat.kapatici.ekip_kapatti(g, kim)
            return {"gorev_id": g.id, "durum": g.durum.value}

    def harita(self) -> list[dict]:
        """Kamuya acik harita: mahalle duzeyinde TOPLULASTIRILMIS.

        Kisisel veri icermez; bina, kat, iletisim ve ham metin disaridadir.
        Bu kirpma yonlendirme matrisinin kamu satiriyla ayni kuraldir.
        """
        with self.kilit:
            kuyruk = self.hat.kuyruk()
        kova: dict[tuple, dict] = {}
        for g in kuyruk:
            if g.durum not in (Durum.DOGRULANDI, Durum.EKIP_ATANDI):
                continue
            k = g.konum
            if k.lat is None:
                continue
            anahtar = (k.il, k.ilce, k.mahalle)
            kayit = kova.setdefault(anahtar, {
                "il": k.il, "ilce": k.ilce, "mahalle": k.mahalle,
                "lat": k.lat, "lon": k.lon, "gorev": 0, "en_yuksek": 0.0,
            })
            kayit["gorev"] += 1
            kayit["en_yuksek"] = max(kayit["en_yuksek"], round(g.oncelik, 3))
        return sorted(kova.values(), key=lambda x: -x["gorev"])

    def seffaflik(self) -> list[dict]:
        with self.kilit:
            return self.hat.kesici.seffaflik_raporu()

    def sevk_dagilimi(self) -> dict:
        with self.kilit:
            sevkler = self.hat.tum_sevkler()
        d: dict[str, int] = {}
        for s in sevkler:
            d[s.alici.value] = d.get(s.alici.value, 0) + 1
        return {a.value: d.get(a.value, 0) for a in Alici}


OTURUM = Oturum()


class Istek(BaseHTTPRequestHandler):
    def log_message(self, bicim, *args):  # sessiz
        pass

    # --- yardimcilar ---

    def _json(self, veri, kod=200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self) -> dict:
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if not uzunluk:
            return {}
        try:
            return json.loads(self.rfile.read(uzunluk).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # --- yonlendirme ---

    def do_GET(self):
        yol = urlparse(self.path)
        p = yol.path
        if p in ("/", "/api"):
            return self._json({
                "servis": "SES VER",
                "uc_noktalar": ["/api/ozet", "/api/kuyruk", "/api/gorev/<id>",
                                "/api/harita", "/api/seffaflik", "/api/sevk"],
            })

        sorgu = parse_qs(yol.query)
        if p == "/api/ozet":
            return self._json(OTURUM.ozet())
        if p == "/api/kuyruk":
            limit = int(sorgu.get("limit", ["50"])[0])
            return self._json(OTURUM.kuyruk(limit))
        if p.startswith("/api/gorev/"):
            g = OTURUM.gorev(p.rsplit("/", 1)[-1])
            return self._json(g or {"hata": "bulunamadi"}, 200 if g else 404)
        if p == "/api/harita":
            return self._json(OTURUM.harita())
        if p == "/api/seffaflik":
            return self._json(OTURUM.seffaflik())
        if p == "/api/sevk":
            return self._json(OTURUM.sevk_dagilimi())
        return self._json({"hata": "bilinmeyen uc nokta"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        govde = self._govde()
        if p == "/api/cagri":
            return self._json(OTURUM.cagri_ekle(govde))
        if p == "/api/demo":
            adet = max(1, min(int(govde.get("adet", 1000)), 20_000))
            return self._json(OTURUM.demo_besle(adet))
        if p == "/api/sifirla":
            OTURUM.sifirla()
            return self._json({"durum": "sifirlandi"})
        if p.startswith("/api/gorev/") and p.endswith("/kapat"):
            gid = p.split("/")[3]
            return self._json(OTURUM.kapat(gid, govde.get("kim", "saha ekibi")))
        return self._json({"hata": "bilinmeyen uc nokta"}, 404)


def calistir(port: int = 8000, adres: str = "127.0.0.1") -> None:
    sunucu = ThreadingHTTPServer((adres, port), Istek)
    print(f"\n  SES VER paneli:  http://{adres}:{port}\n")
    print("  Kapatmak icin Ctrl+C\n")
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\n  kapatiliyor...")
    finally:
        sunucu.server_close()

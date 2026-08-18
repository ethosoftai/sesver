"""Zehirleme testi - saldirgan altinda bastirma olcumu.

Jurinin soracagi soru sudur: "Sisteme kasitli sahte ihbar yagdirirsam ne olur?"

Test, akisa YER GERCEGI BILINEN sahte kayitlar enjekte eder ve iki seyi ayni
anda olcer:

  1. Sahte kayitlar kuyrukta ne kadar asagi itildi?
  2. Gercek kayitlar bu sirada zarar gordu mu?

Ikincisi olmadan birincisi anlamsizdir: her seyi bastiran bir sistem de
"basarili" gorunurdu. Basari, sahteyi asagi iterken gercege dokunmamaktir.

Saldirgan modeli, 2024 Noto depreminde gozlenen desene dayanir: yeni acilmis
hesaplar, var olmayan adresler, yuksek paylasim baskisi.
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass

from ..data.synth import AkisUreteci
from ..pipeline.graph import BoruHatti
from ..schemas import Hesap, Mesaj

SALDIRI_KALIPLARI = (
    "ACIL {yer} mah {sokak}. sokak {bina} apartmani {kat}. kat {kisi} kisi enkaz altinda PAYLASIN",
    "YARDIM EDIN {yer} mah {sokak}. sok {bina} apt herkes paylassin cok acil",
    "{yer} mahallesi {sokak}. sokak {bina} sitesi coktu {kisi} kisi iceride ACIL RT",
)

# Iki saldirgan modeli:
#
#   "kolay"   - uydurma mahalle adi (2024 Noto deseni). Adres sozlukte yok,
#               kayit konumlanamaz ve gorev kuyruguna hic giremez.
#   "gercekci"- saldirgan UAVT'den gercek mahalle ve sokak adi kullanir.
#               Adres cozulur, kayit kuyruga girer. Bastirmayi bu durumda
#               yalnizca hesap sinyalleri ve ucgenlemenin yoklugu saglar.
#
# Durustluk notu: yalnizca "kolay" modda olculen bir bastirma sonucu
# yaniltici olur. Varsayilan mod bu yuzden "gercekci"dir.
SALDIRGAN_MODLARI = ("kolay", "gercekci")


@dataclass(slots=True)
class ZehirlemeSonucu:
    mod: str
    enjekte: int
    kuyruk_boyu: int
    yakalanan_sahte_gorev: int
    ilk_100: int
    ilk_10: int
    medyan_yuzdelik: float
    temiz_kosum_ilk_100: int
    gercek_gorev_kaybi: int
    sure_sn: float

    def yazdir(self) -> str:
        return "\n".join(
            [
                "",
                "=" * 66,
                f"  ZEHIRLEME TESTI - saldirgan modeli: {self.mod}",
                "=" * 66,
                "",
                f"    enjekte edilen sahte kayit   {self.enjekte}",
                f"    kuyruk boyu                  {self.kuyruk_boyu}",
                f"    kuyruga giren sahte gorev    {self.yakalanan_sahte_gorev}",
                "",
                f"    ilk 10'a sizan               {self.ilk_10}      <- hedef 0",
                f"    ilk 100'e sizan              {self.ilk_100}",
                f"    medyan yuzdelik              {self.medyan_yuzdelik:.3f}  "
                "<- 1.0 = kuyrugun dibi",
                "",
                f"    zehirsiz kosumda ilk 100     {self.temiz_kosum_ilk_100}",
                f"    kaybolan GERCEK gorev        {self.gercek_gorev_kaybi}      <- hedef 0",
                "",
                f"    sure                         {self.sure_sn:.2f} sn",
                "",
                "=" * 66,
                "",
            ]
        )


def kosum(
    mesaj_sayisi: int = 20_000,
    zehir: int = 200,
    seed: int = 13,
    mod: str = "gercekci",
) -> ZehirlemeSonucu:
    if mod not in SALDIRGAN_MODLARI:
        raise ValueError(f"bilinmeyen saldirgan modeli: {mod}")
    rnd = random.Random(seed)
    ureteci = AkisUreteci(seed=seed)
    akis = ureteci.uret(mesaj_sayisi)

    # --- 1) temiz kosum: karsilastirma tabani ---
    temiz = BoruHatti()
    for m in akis.mesajlar:
        temiz.isle(m)
    temiz_kuyruk = temiz.kuyruk()
    temiz_gercek = {
        g.konum.anahtar()
        for g in temiz_kuyruk[:100]
        if any(c.mesaj.id in akis.mesaj_olay for c in g.cagrilar)
    }

    # --- 2) zehirli kosum ---
    zehirli_idler: set[str] = set()
    mesajlar = list(akis.mesajlar)
    taban_ts = mesajlar[len(mesajlar) // 2].ts
    for i in range(zehir):
        kalip = rnd.choice(SALDIRI_KALIPLARI)
        # Gercekci saldirgan sozlukteki gercek mahalle adlarini kullanir.
        yer = (
            rnd.choice(ureteci._mahalleler)
            if mod == "gercekci"
            else rnd.choice(("mavikent", "yesilkent", "altinkent", "beyazkent"))
        )
        metin = kalip.format(
            yer=yer,
            sokak=rnd.randint(1, 200),
            bina=rnd.choice(("ozgur", "deniz", "kartal", "sahin")),
            kat=rnd.randint(1, 12),
            kisi=rnd.randint(2, 9),
        )
        mid = f"Z-{i:05d}"
        zehirli_idler.add(mid)
        mesajlar.append(
            Mesaj(
                id=mid,
                metin=metin,
                hesap=Hesap(
                    id=f"bot{rnd.randint(1, 9999)}",
                    yas_gun=rnd.randint(0, 4),
                    takipci=rnd.randint(0, 30),
                    bolgede_gecmis=False,
                ),
                ts=taban_ts + rnd.uniform(0, 3600),
                paylasim=rnd.randint(500, 9000),
            )
        )
    mesajlar.sort(key=lambda m: m.ts)

    t0 = time.perf_counter()
    hat = BoruHatti()
    for m in mesajlar:
        hat.isle(m)
    kuyruk = hat.kuyruk()
    sure = time.perf_counter() - t0

    n = max(len(kuyruk), 1)
    yuzdelikler: list[float] = []
    ilk_100 = ilk_10 = 0
    for sira, g in enumerate(kuyruk):
        if any(c.mesaj.id in zehirli_idler for c in g.cagrilar):
            yuzdelikler.append(sira / n)
            ilk_100 += sira < 100
            ilk_10 += sira < 10

    # Gercek gorev kaybi: temiz kosumun ilk 100'undeki adresler zehirli
    # kosumda kuyrukta hala var mi?
    zehirli_adresler = {g.konum.anahtar() for g in kuyruk}
    kayip = len(temiz_gercek - zehirli_adresler)

    return ZehirlemeSonucu(
        mod=mod,
        enjekte=zehir,
        kuyruk_boyu=len(kuyruk),
        yakalanan_sahte_gorev=len(yuzdelikler),
        ilk_100=ilk_100,
        ilk_10=ilk_10,
        medyan_yuzdelik=round(statistics.median(yuzdelikler), 3) if yuzdelikler else 1.0,
        temiz_kosum_ilk_100=len(temiz_gercek),
        gercek_gorev_kaybi=kayip,
        sure_sn=round(sure, 3),
    )

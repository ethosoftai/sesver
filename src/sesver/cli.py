"""Komut satiri arayuzu.

    python -m sesver.cli demo     # canli akis simulasyonu
    python -m sesver.cli bench    # SES VER-Bench tam kosum
    python -m sesver.cli poison   # zehirleme testi
    python -m sesver.cli sevk     # yonlendirme matrisini goster

Hicbiri harici bagimlilik istemez.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

from .data.synth import AkisUreteci
from .eval import altin_set, bench, poison
from .pipeline.graph import BoruHatti


def _demo(args: argparse.Namespace) -> int:
    akis = AkisUreteci(seed=args.seed).uret(args.messages)
    hat = BoruHatti()

    print(f"\n  akis: {len(akis.mesajlar)} mesaj, {len(akis.olaylar)} yer-gercegi olayi\n")
    t0 = time.perf_counter()
    for m in akis.mesajlar:
        hat.isle(m)
    kuyruk = hat.kuyruk()
    sure = time.perf_counter() - t0
    o = hat.ozet()

    print(f"  {o['mesaj']} mesaj -> {o['gorev']} gorev   ({sure * 1000:.0f} ms, "
          f"{o['mesaj'] / max(sure, 1e-9):,.0f} mesaj/sn)")
    print(f"  cagri {o['cagri']} | iddia {o['iddia']} | destek {o['destek']} | "
          f"gurultu {o['gurultu']} | konumsuz {o['konumsuz']}")
    print(f"  devre kesici: {o['kesici_acilan']} acildi, {o['kesici_cozulen']} cozuldu")
    print(
        f"  bildirim (mail): {o['mail_gonderilen']} gonderildi, "
        f"{o['mail_basarisiz']} atlandi/basarisiz "
        f"(SESVER_MAIL_ENABLED=1 ile acilir)\n"
    )

    print("  KUYRUK - ilk 10")
    print("  " + "-" * 92)
    print(f"  {'gorev':10s} {'onc':>6s} {'guven':>6s} {'durum':13s} {'kaynak':>6s} adres")
    print("  " + "-" * 92)
    for g in kuyruk[:10]:
        k = g.konum
        adres = f"{k.ilce or '?'} / {k.mahalle or '?'} / {k.sokak or '-'} / {k.bina or '-'}"
        print(f"  {g.id:10s} {g.oncelik:6.3f} {g.guven:6.2f} {g.durum.value:13s} "
              f"{g.bagimsiz_kaynak:6d} {adres}")
    print()

    sevkler = hat.tum_sevkler()
    dagilim = Counter(s.alici.value for s in sevkler)
    print("  SEVK DAGILIMI")
    for alici, adet in dagilim.most_common():
        print(f"    {alici:22s} {adet:6d}")

    if hat.kesici.gunluk:
        print("\n  SEFFAFLIK GUNLUGU - ilk 5 devre kesici karari")
        for kayit in hat.kesici.seffaflik_raporu()[:5]:
            print(f"    {kayit['iddia_id']} {kayit['tur']:10s} etki={kayit['etki']:.2f} "
                  f"sure={kayit['sure_sn']}sn -> {str(kayit['sonuc'])[:46]}")
    print()
    return 0


def _bench(args: argparse.Namespace) -> int:
    rapor, _ = bench.kosum(mesaj_sayisi=args.messages, seed=args.seed,
                          gurultu=args.gurultu)
    print(rapor.yazdir())
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rapor.sozluk(), f, ensure_ascii=False, indent=2)
        print(f"  json yazildi: {args.json}\n")
    return 0


def _poison(args: argparse.Namespace) -> int:
    sonuc = poison.kosum(
        mesaj_sayisi=args.messages, zehir=args.poison, seed=args.seed, mod=args.mode
    )
    print(sonuc.yazdir())
    return 0


def _altin_set(args: argparse.Namespace) -> int:
    rapor = altin_set.kosum()
    print(rapor.yazdir())
    if rapor.anma is None:
        print(
            "  ipucu: metin icin X API Bearer token gerekir.\n"
            "  export SESVER_X_BEARER_TOKEN=... ile calistirin.\n"
        )
    return 0


def _sevk(args: argparse.Namespace) -> int:
    akis = AkisUreteci(seed=args.seed).uret(args.messages)
    hat = BoruHatti()
    for m in akis.mesajlar:
        hat.isle(m)
    kuyruk = hat.kuyruk()
    if not kuyruk:
        print("kuyruk bos")
        return 1
    gorev = kuyruk[0]
    print(f"\n  ORNEK GOREV {gorev.id} icin yonlendirme\n")
    for s in hat.yonlendirici.gorev_sevkleri(gorev):
        print(f"  -> {s.alici.value}")
        print(f"     gerekce: {s.gerekce}")
        print(f"     alanlar: {sorted(s.yuk)}")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(
        prog="sesver",
        description="SES VER - afet aninda sosyal medya triyaj ve dogrulama katmani",
    )
    alt = ayrac.add_subparsers(dest="komut", required=True)

    def ortak(p):
        p.add_argument("--messages", type=int, default=3000, help="uretilecek mesaj sayisi")
        p.add_argument("--seed", type=int, default=42, help="yeniden uretilebilirlik icin")
        return p

    ortak(alt.add_parser("demo", help="canli akis simulasyonu")).set_defaults(fn=_demo)

    b = ortak(alt.add_parser("bench", help="SES VER-Bench tam kosum"))
    b.add_argument("--json", help="metrikleri json olarak yaz")
    b.add_argument("--gurultu", type=float, default=1.0,
                   help="yazim bozulmasi siddeti; 0 = temiz sablon ciktisi")
    b.set_defaults(fn=_bench)

    p = ortak(alt.add_parser("poison", help="zehirleme testi"))
    p.add_argument("--poison", type=int, default=200, help="enjekte edilecek sahte kayit")
    p.add_argument(
        "--mode",
        choices=("gercekci", "kolay"),
        default="gercekci",
        help="saldirgan modeli: gercek adres kullanan (varsayilan) veya uydurma adres",
    )
    p.set_defaults(fn=_poison)

    ortak(alt.add_parser("sevk", help="yonlendirme matrisini goster")).set_defaults(fn=_sevk)

    alt.add_parser(
        "altin-set", help="bagimsiz gercek veri (Toraman ve ark. 2023) uzerinde dogrulama"
    ).set_defaults(fn=_altin_set)

    args = ayrac.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

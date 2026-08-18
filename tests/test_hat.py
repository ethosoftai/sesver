"""Boru hattinin davranis sozlesmeleri."""

from __future__ import annotations

import time

import pytest

from sesver.claims.breaker import DevreKesici
from sesver.claims.detect import IddiaTespitci
from sesver.claims.impact import etki_hesapla
from sesver.data.synth import AkisUreteci
from sesver.metin import normalize, yakin_esles
from sesver.pipeline.dedup import Birlestirici, haversine_m
from sesver.pipeline.extract import Cozumleyici
from sesver.pipeline.graph import BoruHatti
from sesver.pipeline.prioritize import oncelik_hesapla
from sesver.pipeline.triage import KuralTriyaj
from sesver.pipeline.verify import Durus, durus_belirle
from sesver.schemas import (
    Cagri,
    Cozunurluk,
    Gorev,
    Hesap,
    Konum,
    Mesaj,
    Mod,
    Tur,
)


# --- metin ---


def test_turkce_katlama() -> None:
    assert normalize("Kızım ENKAZ altında!!!") == "kizim enkaz altinda"
    assert normalize("yardimmmmm") == "yardimm"


def test_yakin_esles_yazim_hatasina_dayanikli() -> None:
    assert yakin_esles("armutlu", ["Armutlu", "Sumerler"]) == "Armutlu"
    assert yakin_esles("zzzzzz", ["Armutlu"]) is None


# --- triyaj ---


@pytest.mark.parametrize(
    "metin,beklenen",
    [
        ("antakya armutlu mah 5. sok yilmaz apt 3. kat enkaz altindayiz", Tur.CAGRI),
        ("BARAJ PATLADI HERKES YUKSEK YERE KACSIN", Tur.IDDIA),
        ("gecmis olsun rabbim yardimcisi olsun", Tur.GURULTU),
        ("elimde 200 battaniye var yardim edebilirim kamyonet de var", Tur.DESTEK),
    ],
)
def test_triyaj_siniflari(metin: str, beklenen: Tur) -> None:
    tur, _ = KuralTriyaj()(Mesaj(id="m", metin=metin, hesap=Hesap(id="h")))
    assert tur is beklenen


def test_triyaj_anma_yanlisi_cagri_lehine_egiyor() -> None:
    """Karasiz kalinan mesaj CAGRI kabul edilmeli: kacirmak elemekten kotudur."""
    tur, _ = KuralTriyaj()(Mesaj(id="m", metin="yardim lazim", hesap=Hesap(id="h")))
    assert tur is Tur.CAGRI


# --- adres cikarimi ---


def test_yapi_sozcugu_bina_adi_olarak_alinmaz() -> None:
    """'siteler mah bina coktu' ifadesinde bina adi 'mah' degildir."""
    c = Cozumleyici()
    g = c(Mesaj(id="m", metin="ADIYAMAN SITELER MAH. BINA COKTU", hesap=Hesap(id="h")))
    assert g.konum.bina is None
    assert g.konum.mahalle == "Siteler"


def test_tam_adres_bina_cozunurlugu_verir() -> None:
    c = Cozumleyici()
    g = c(
        Mesaj(
            id="m",
            metin="antakya armutlu mah 5. sok yilmaz apt 3. kat 4 kisiyiz sesler geliyor",
            hesap=Hesap(id="h"),
        )
    )
    assert g.konum.cozunurluk is Cozunurluk.BINA
    assert (g.konum.mahalle, g.konum.sokak, g.konum.bina) == ("Armutlu", "5. Sokak", "Yilmaz")
    assert g.kisi_sayisi == 4
    assert g.ses_var is True


def test_cihaz_konumu_en_guvenilir_sinyaldir() -> None:
    c = Cozumleyici()
    g = c(
        Mesaj(
            id="m",
            metin="yardim edin",
            hesap=Hesap(id="h"),
            konum_etiketi=(36.2, 36.15),
        )
    )
    assert g.konum.cozunurluk is Cozunurluk.BINA
    assert g.konum.guven >= 0.9


# --- tekillestirme ---


def _cagri(metin: str, hesap: str, ts: float) -> Cagri:
    return Cozumleyici()(Mesaj(id=f"{hesap}-{ts}", metin=metin, hesap=Hesap(id=hesap), ts=ts))


def test_ayni_olay_tek_goreve_iner() -> None:
    b = Birlestirici()
    t0 = time.time()
    b.ekle(_cagri("antakya armutlu mah 5. sok yilmaz apt 3. kat 4 kisiyiz", "h1", t0))
    b.ekle(_cagri("ANTAKYA ARMUTLU MAH 5 SOK YILMAZ APARTMANI 3 KAT ACIL", "h2", t0 + 60))
    assert len(b.gorevler) == 1
    assert next(iter(b.gorevler.values())).bagimsiz_kaynak == 2


def test_farkli_bina_birlesmez() -> None:
    """Metin benzerligi adres celiskisinin yerine gecmez."""
    b = Birlestirici()
    t0 = time.time()
    b.ekle(_cagri("antakya armutlu mah 5. sok yilmaz apt 3. kat 4 kisiyiz", "h1", t0))
    b.ekle(_cagri("antakya armutlu mah 5. sok gunes apt 3. kat 4 kisiyiz", "h2", t0 + 60))
    assert len(b.gorevler) == 2


def test_konumsuz_cagri_gorev_acmaz() -> None:
    b = Birlestirici()
    assert b.ekle(_cagri("yardim edin acil", "h1", time.time())) is None
    assert len(b.gorevler) == 0
    assert len(b.konumsuz) == 1


def test_haversine_makul() -> None:
    assert 900 < haversine_m(36.2077, 36.1524, 36.2005, 36.1580) < 1000


# --- durus ---


@pytest.mark.parametrize(
    "metin,beklenen",
    [
        ("kurtarildilar cok sukur", Durus.COZULDU),
        ("boyle bir adres yok arkadaslar", Durus.YALANLAMA),
        ("ben de gordum komsusuyum", Durus.TEYIT),
        ("dogru mu acaba", Durus.SORGU),
        ("saat kac", Durus.ILGISIZ),
    ],
)
def test_durus_siniflari(metin: str, beklenen: Durus) -> None:
    assert durus_belirle(Mesaj(id="y", metin=metin, hesap=Hesap(id="h"))) is beklenen


# --- oncelik ---


def _gorev(ses: bool, kirilgan: bool, guven: float, coz: Cozunurluk) -> Gorev:
    t0 = time.time()
    konum = Konum(cozunurluk=coz)
    g = Gorev(id="G", konum=konum, olusma_ts=t0 - 7200, son_teyit_ts=t0)
    g.cagrilar = [
        Cagri(
            mesaj=Mesaj(id="m", metin="x", hesap=Hesap(id="h"), ts=t0),
            konum=konum,
            kisi_sayisi=3,
            kirilgan=kirilgan,
            ses_var=ses,
        )
    ]
    g.guven = guven
    return g


def test_dusuk_guvenli_yuksek_riskli_cagri_gomulmez() -> None:
    """Guven bir SIRALAMA carpanidir, ELEME kapisi degil."""
    simdi = time.time()
    riskli = _gorev(ses=True, kirilgan=True, guven=0.36, coz=Cozunurluk.BINA)
    sakin = _gorev(ses=False, kirilgan=False, guven=0.92, coz=Cozunurluk.BINA)
    assert oncelik_hesapla(riskli, simdi) > oncelik_hesapla(sakin, simdi)


# --- B hatti ---


def test_nesne_tek_basina_iddia_degildir() -> None:
    t = IddiaTespitci()
    assert t.iddia_mi("baraj patladi") is True
    assert t.iddia_mi("barajda bakim calismasi yapiliyor") is False


def test_kesici_yalnizca_afet_modunda_calisir() -> None:
    """Kilit 4: normal modda mekanizma kapalidir."""
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    assert iddia is not None
    etki_hesapla(iddia, 900)
    assert DevreKesici(mod=Mod.NORMAL).ac(iddia) is False
    assert DevreKesici(mod=Mod.AFET).ac(iddia) is True


def test_kesici_gunlugu_kamuya_acik() -> None:
    """Kilit 3: her kesici karari gerekcesiyle kayitlidir."""
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    k = DevreKesici(mod=Mod.AFET)
    etki_hesapla(iddia, 900)
    k.ac(iddia, simdi=0.0)
    k.coz(iddia, "su seviyesi normal", "DSI - otomatik telemetri - 14:32", simdi=11.0)
    rapor = k.seffaflik_raporu()
    assert len(rapor) == 1 and rapor[0]["sure_sn"] == 11.0


def test_yanitsiz_kurum_kesiciyi_dusurur() -> None:
    """Sessizlik kalici kisitlamanin gerekcesi olamaz."""
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    k = DevreKesici(mod=Mod.AFET)
    etki_hesapla(iddia, 900)
    k.ac(iddia, simdi=0.0)
    k.yanitsiz(iddia, simdi=901.0)
    assert iddia.kesici.value == "yanitsiz"


# --- uctan uca ---


def test_uctan_uca_kosum_belirlenimci() -> None:
    """Ayni tohum ayni cikti: kurtarma kararlari yeniden uretilebilir olmali."""
    akis = AkisUreteci(seed=5).uret(1200)
    ozetler = []
    for _ in range(2):
        hat = BoruHatti()
        for m in akis.mesajlar:
            hat.isle(m)
        kuyruk = hat.kuyruk()
        ozetler.append([(g.id, g.oncelik) for g in kuyruk[:20]])
    assert ozetler[0] == ozetler[1]


def test_uctan_uca_hicbir_gercek_cagri_kaybolmaz() -> None:
    akis = AkisUreteci(seed=9).uret(2000)
    hat = BoruHatti()
    for m in akis.mesajlar:
        hat.isle(m)
    hat.kuyruk()
    islenen = sum(len(g.cagrilar) for g in hat.birlestirici.gorevler.values())
    assert islenen + len(hat.birlestirici.konumsuz) == hat.sayac.cagri

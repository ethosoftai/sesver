"""Gizlilik sinirlarini koruyan testler.

Bu dosya bir tasarim sozlesmesidir. Yonlendirme matrisinde kisisel veriyi
yanlis aliciya sizdiran her degisiklik burayi kirar.
"""

from __future__ import annotations

import pytest

from sesver.pipeline.route import KISISEL_ALANLAR, Yonlendirici
from sesver.schemas import (
    Alici,
    Cagri,
    Cozunurluk,
    Durum,
    Gorev,
    Hesap,
    Iddia,
    IddiaTuru,
    KesiciDurum,
    Konum,
    Mesaj,
)


@pytest.fixture
def gorev() -> Gorev:
    konum = Konum(
        il="Hatay",
        ilce="Antakya",
        mahalle="Armutlu",
        sokak="5. Sokak",
        bina="Yilmaz",
        kat=3,
        lat=36.2077,
        lon=36.1524,
        cozunurluk=Cozunurluk.BINA,
        guven=0.86,
    )
    g = Gorev(id="G-1", konum=konum, guven=0.93, oncelik=0.5, durum=Durum.DOGRULANDI)
    g.cagrilar = [
        Cagri(
            mesaj=Mesaj(id="m1", metin="enkaz altindayiz", hesap=Hesap(id="h1")),
            konum=konum,
            kisi_sayisi=4,
            kirilgan=True,
            ses_var=True,
            aciklama="enkaz altindayiz 4 kisiyiz",
        ),
        Cagri(
            mesaj=Mesaj(id="m2", metin="ayni bina", hesap=Hesap(id="h2")),
            konum=konum,
            aciklama="ayni bina",
        ),
    ]
    return g


def test_kamuya_kisisel_veri_gitmez(gorev: Gorev) -> None:
    """Halka acik haritada isim, kat, bina, koordinat ve iletisim olmamali."""
    sevkler = Yonlendirici().gorev_sevkleri(gorev)
    kamu = [s for s in sevkler if s.alici is Alici.KAMU]
    assert kamu, "dogrulanmis gorev kamu haritasina dusmeli"
    for s in kamu:
        sizan = KISISEL_ALANLAR & set(s.yuk)
        assert not sizan, f"kamu yukunde kisisel alan sizdi: {sizan}"


def test_valilik_toplulastirilmis_gorur(gorev: Gorev) -> None:
    sevkler = Yonlendirici().gorev_sevkleri(gorev)
    for s in sevkler:
        if s.alici is Alici.VALILIK:
            assert not (KISISEL_ALANLAR & set(s.yuk))


def test_gonulluye_iletisim_bilgisi_gitmez(gorev: Gorev) -> None:
    """Gonullu dogrular ama cagri sahibinin iletisimini gormez."""
    gorev.guven = 0.60  # belirsiz bant
    sevkler = Yonlendirici().gorev_sevkleri(gorev)
    gonullu = [s for s in sevkler if s.alici is Alici.GONULLU]
    assert gonullu
    for s in gonullu:
        assert "iletisim" not in s.yuk


def test_afad_ve_saha_tam_veri_alir(gorev: Gorev) -> None:
    """Yetkili alicilar gorevi yapabilmek icin tam kaydi gorur."""
    sevkler = Yonlendirici().gorev_sevkleri(gorev)
    afad = next(s for s in sevkler if s.alici is Alici.AFAD)
    assert "koordinat" in afad.yuk and "iletisim" in afad.yuk


def test_kolluga_dogrulanmamis_ihbar_gitmez() -> None:
    """Pazarlik disi kural: acik bir asayis iddiasi kolluga gitmez."""
    iddia = Iddia(
        id="I-1",
        mesaj=Mesaj(id="m", metin="yagma basladi", hesap=Hesap(id="h")),
        tur=IddiaTuru.ASAYIS,
        kesici=KesiciDurum.ACIK,
    )
    sevkler = Yonlendirici().iddia_sevkleri(iddia)
    assert not [s for s in sevkler if s.alici is Alici.KOLLUK]


def test_kolluga_yalnizca_cozulmus_olay_gider() -> None:
    iddia = Iddia(
        id="I-2",
        mesaj=Mesaj(id="m", metin="yagma basladi", hesap=Hesap(id="h")),
        tur=IddiaTuru.ASAYIS,
        kesici=KesiciDurum.COZULDU,
        sonuc="Valilik: bolgede asayis olayi kaydedilmedi.",
    )
    sevkler = Yonlendirici().iddia_sevkleri(iddia)
    kolluk = [s for s in sevkler if s.alici is Alici.KOLLUK]
    assert len(kolluk) == 1
    assert "sonuc" in kolluk[0].yuk

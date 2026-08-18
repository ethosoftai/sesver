"""BILDIR katmani: etiketlenen kayitlar mail ile bildirilir, platforma yazilmaz."""

from __future__ import annotations

import time

from sesver.bildirim import Bildirimci, MailAyarlari
from sesver.claims.detect import IddiaTespitci
from sesver.claims.impact import etki_hesapla
from sesver.schemas import Cozunurluk, Gorev, Hesap, Konum, Mesaj


def _sahte_gonderici(kutular: list[tuple[str, str, str]]):
    def gonder(ayar, alici: str, konu: str, govde: str) -> None:
        kutular.append((alici, konu, govde))

    return gonder


def _acik_ayar() -> MailAyarlari:
    return MailAyarlari(etkin=True, varsayilan_alici="afad-koordinasyon@ornek.gov.tr")


def test_varsayilan_olarak_mail_atmaz() -> None:
    """Ortam degiskeni verilmedigi surece hicbir ag istegi yapilmamali."""
    kutular: list[tuple[str, str, str]] = []
    b = Bildirimci(gonderici=_sahte_gonderici(kutular))
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    assert iddia is not None
    etki_hesapla(iddia, 900)

    assert b.iddia_tespit_edildi(iddia) is False
    assert kutular == []
    assert b.gunluk[-1].basarili is False


def test_iddia_turune_gore_dogru_kutuya_gider() -> None:
    kutular: list[tuple[str, str, str]] = []
    b = Bildirimci(ayar=_acik_ayar(), gonderici=_sahte_gonderici(kutular))
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    assert iddia is not None
    etki_hesapla(iddia, 900)

    assert b.iddia_tespit_edildi(iddia) is True
    assert kutular[0][0] == "dsi-izleme@ornek.gov.tr"
    assert "baraj" in kutular[0][1]


def test_gonderim_basarisiz_olursa_hat_susmaz() -> None:
    """Fail-open: mail cikmazi bir istisna olarak yukselmez, gunluge duser."""

    def patlayan(ayar, alici, konu, govde):
        raise ConnectionRefusedError("smtp yok")

    b = Bildirimci(ayar=_acik_ayar(), gonderici=patlayan)
    t = IddiaTespitci()
    iddia = t(Mesaj(id="m", metin="baraj patladi herkes kacsin", hesap=Hesap(id="h")))
    assert iddia is not None
    etki_hesapla(iddia, 900)

    assert b.iddia_tespit_edildi(iddia) is False
    assert b.gunluk[-1].basarili is False
    assert "smtp yok" in (b.gunluk[-1].hata or "")


def _gorev(oncelik: float) -> Gorev:
    t0 = time.time()
    g = Gorev(id="G-1", konum=Konum(cozunurluk=Cozunurluk.BINA), olusma_ts=t0, son_teyit_ts=t0)
    g.oncelik = oncelik
    return g


def test_yuksek_oncelikli_gorev_esik_altinda_mail_atmaz() -> None:
    kutular: list[tuple[str, str, str]] = []
    b = Bildirimci(ayar=_acik_ayar(), gonderici=_sahte_gonderici(kutular))
    assert b.gorev_yuksek_oncelik(_gorev(0.30)) is False
    assert kutular == []


def test_yuksek_oncelikli_gorev_bir_kez_bildirilir() -> None:
    kutular: list[tuple[str, str, str]] = []
    b = Bildirimci(ayar=_acik_ayar(), gonderici=_sahte_gonderici(kutular))
    gorev = _gorev(0.90)

    assert b.gorev_yuksek_oncelik(gorev) is True
    assert b.gorev_yuksek_oncelik(gorev) is False  # ayni gorev tekrar mail atmaz
    assert len(kutular) == 1

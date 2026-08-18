"""DIVAN-COZ SFT veri uretimi: etiketler Cozumleyici degil, yer gercegidir."""

from __future__ import annotations

from sesver.models.sft_veri import uret


def test_uretilen_alanlar_semaya_uyar() -> None:
    ornekler = uret(mesaj_sayisi=1500, seed=1)
    assert ornekler
    beklenen_anahtarlar = {
        "il", "ilce", "mahalle", "sokak", "bina", "kat",
        "kisi_sayisi", "kirilgan", "ses_var",
    }
    for o in ornekler:
        assert o["mesaj"]
        assert set(o["alanlar"]) == beklenen_anahtarlar


def test_sahte_mahalle_null_degil_metindeki_haliyle_yazilir() -> None:
    """Sahte kampanyada il/ilce cozulemez (null) ama mahalle metinden cikarilir."""
    ornekler = uret(mesaj_sayisi=3000, seed=2)
    sahte_ornekler = [o for o in ornekler if o["alanlar"]["il"] is None]
    assert sahte_ornekler, "test veri hacminde en az bir sahte kayit bekleniyor"
    for o in sahte_ornekler:
        assert o["alanlar"]["ilce"] is None
        assert o["alanlar"]["mahalle"]  # None degil, bos degil


def test_belirlenimci() -> None:
    a = uret(mesaj_sayisi=1000, seed=7)
    b = uret(mesaj_sayisi=1000, seed=7)
    assert a == b

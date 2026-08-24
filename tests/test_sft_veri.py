"""DIVAN-COZ SFT veri uretimi: etiketler Cozumleyici degil, yer gercegidir."""

from __future__ import annotations

import re

from sesver.metin import normalize
from sesver.models.sft_veri import uret

BEKLENEN_ANAHTARLAR = {
    "il", "ilce", "mahalle", "sokak", "bina", "kat",
    "kisi_sayisi", "kirilgan", "ses_var",
}


def test_uretilen_alanlar_semaya_uyar() -> None:
    ornekler = uret(mesaj_sayisi=1500, seed=1)
    assert ornekler
    for o in ornekler:
        assert o["mesaj"]
        assert set(o["alanlar"]) == BEKLENEN_ANAHTARLAR


def test_metinde_gecmeyen_alan_etiketlenmez() -> None:
    """En kritik veri kalitesi sozlesmesi.

    Uretecin yer gercegi olayin tamamini bilir ama her sablon hepsini
    yazmaz; ustelik yazim bozulmasi yazilanlarin bir kismini taninmaz hale
    getirir. Metinde bulunmayan bir alani etiketlemek, modele bilgi
    UYDURMAYI ogretir - bir afet sisteminde en tehlikeli davranis budur.
    """
    ornekler = uret(mesaj_sayisi=4000, seed=3)
    for o in ornekler:
        n = normalize(o["mesaj"])
        a = o["alanlar"]
        if a["mahalle"]:
            assert normalize(a["mahalle"]) in n
        if a["bina"]:
            assert normalize(a["bina"]) in n
        if a["kat"] is not None:
            assert re.search(rf"\b{a['kat']}\s*kat", n)
        if a["kisi_sayisi"] is not None:
            assert re.search(rf"\b{a['kisi_sayisi']}\s*kisi", n)


def test_sahte_mahalle_metinde_varsa_yazilir_null_degil() -> None:
    """Sahte kampanyada il/ilce cozulemez (null) ama mahalle metinden cikarilir.

    Cikti semasi bir METIN CIKARIMIDIR, dogruluk denetimi degil; o denetim
    ayri asamadadir (pipeline/verify.py, data/gazetteer.py). Mahallenin null
    kaldigi tek durum, yazim bozulmasi yuzunden metinde artik taninmamasidir.
    """
    ornekler = uret(mesaj_sayisi=4000, seed=2)
    sahte = [
        o for o in ornekler
        if o["alanlar"]["il"] is None and o["alanlar"]["mahalle"]
    ]
    assert sahte, "test veri hacminde en az bir sahte kayit bekleniyor"
    for o in sahte:
        assert o["alanlar"]["ilce"] is None
        assert normalize(o["alanlar"]["mahalle"]) in normalize(o["mesaj"])


def test_negatif_ornekler_var() -> None:
    """Cagri olmayan mesajlar tum alanlari null olarak etiketlenmeli.

    Bunlar olmadan model her mesajdan adres uydurmayi ogrenir.
    """
    ornekler = uret(mesaj_sayisi=3000, seed=5)
    negatif = [o for o in ornekler if o["alanlar"]["mahalle"] is None
               and o["alanlar"]["bina"] is None]
    assert negatif, "negatif ornek bekleniyor"


def test_belirlenimci() -> None:
    a = uret(mesaj_sayisi=1000, seed=7)
    b = uret(mesaj_sayisi=1000, seed=7)
    assert a == b

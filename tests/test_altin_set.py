"""Bagimsiz altin set: kaynak yukleme ve degerlendirme, ag erisimi olmadan."""

from __future__ import annotations

from sesver.eval.altin_set import KAYNAK_TSV, AltinKayit, degerlendir, kaynak_yukle


def test_kaynak_dosyasi_ham_metin_icermez() -> None:
    """Gizlilik: yalnizca id/etiket/varlik-ofseti; hicbir satirda tweet metni yok."""
    kayitlar = kaynak_yukle()
    assert len(kayitlar) == 1000
    assert all(k.metin is None for k in kayitlar)


def test_kaynak_dosyasi_yolu_repo_kokune_gore_dogru() -> None:
    assert KAYNAK_TSV.exists()


def test_hidratsiz_degerlendirme_yalnizca_dagilim_verir() -> None:
    kayitlar = kaynak_yukle()
    rapor = degerlendir(kayitlar)
    assert rapor.anma is None
    assert rapor.etiket_dagilimi["cagri"] + rapor.etiket_dagilimi["cagri_degil"] == 1000


def test_hidratli_degerlendirme_triyaj_metrigi_uretir() -> None:
    kayitlar = [
        AltinKayit(
            tweet_id="1",
            yardim_cagrisi=True,
            varlik_sayisi=1,
            metin="antakya armutlu mah 5 sok yilmaz apt 3 kat enkaz altindayiz",
        ),
        AltinKayit(tweet_id="2", yardim_cagrisi=False, varlik_sayisi=0, metin="gecmis olsun"),
    ]
    rapor = degerlendir(kayitlar)
    assert rapor.anma is not None
    assert rapor.hidrat_edilen == 2

"""AKTAR - yonlendirme matrisi.

Sistemin en cok tasarim karari tasiyan dosyasi. Her alici FARKLI bir gorunum
alir; kimse ihtiyaci olmayan veriyi gormez.

Iki kural pazarlik disidir:

1. KOLLUGA DOGRULANMAMIS BIREYSEL IHBAR GITMEZ.
   Yalnizca dogrulanmis olaylar ve toplulastirilmis soylenti durumu iletilir.
   Dogrulanmamis bir soylentiyi birey duzeyinde kolluga iletmek yurttas
   haklari acisindan savunulamaz.

2. KAMUYA KISISEL VERI GITMEZ.
   Halka acik harita bina duzeyinde toplulastirilir; isim, telefon ve saglik
   durumu yalnizca gorevi ustlenen ekibe, yalnizca gorev suresince acilir.

Bu iki kural ``tests/test_gizlilik.py`` tarafindan sinanir; ihlal eden bir
degisiklik testi kirar.
"""

from __future__ import annotations

from ..config import ESIK
from ..schemas import Alici, Durum, Gorev, Iddia, IddiaTuru, KesiciDurum, Sevk

# Kamuya ve toplulastirilmis gorunumlere asla girmeyecek alanlar.
KISISEL_ALANLAR = frozenset(
    {"sokak", "bina", "kat", "koordinat", "kisi_sayisi", "kirilgan", "ses_var",
     "iletisim", "metin"}
)


def _ozet(gorev: Gorev, kisisel: bool) -> dict:
    """Gorevin, alicinin yetkisine gore kirpilmis gorunumu."""
    k = gorev.konum
    yuk = {
        "gorev_id": gorev.id,
        "il": k.il,
        "ilce": k.ilce,
        "mahalle": k.mahalle,
        "cozunurluk": k.cozunurluk.value,
        "durum": gorev.durum.value,
        "guven": gorev.guven,
        "oncelik": gorev.oncelik,
        "bagimsiz_kaynak": gorev.bagimsiz_kaynak,
        "kopya": gorev.kopya_sayisi,
    }
    if kisisel:
        yuk.update(
            {
                "sokak": k.sokak,
                "bina": k.bina,
                "kat": k.kat,
                "koordinat": [k.lat, k.lon],
                "kisi_sayisi": max((c.kisi_sayisi or 0) for c in gorev.cagrilar) or None,
                "kirilgan": any(c.kirilgan for c in gorev.cagrilar),
                "ses_var": any(c.ses_var for c in gorev.cagrilar),
                "iletisim": [c.mesaj.hesap.id for c in gorev.cagrilar],
                "metin": [c.aciklama for c in gorev.cagrilar[:3]],
            }
        )
    return yuk


class Yonlendirici:
    """Gorev ve iddialari dogru alicilara paketler."""

    def gorev_sevkleri(self, gorev: Gorev) -> list[Sevk]:
        sevkler: list[Sevk] = []

        # --- AFAD: koordinasyon merkezi, tam yetki ---
        sevkler.append(
            Sevk(
                alici=Alici.AFAD,
                konu="gorev",
                yuk=_ozet(gorev, kisisel=True),
                gerekce="koordinasyon merkezi tam listeyi gorur",
            )
        )

        # --- Saha ekibi: yalnizca eyleme donusturulebilir ve ucgenlenmis kayit ---
        if (
            gorev.guven >= ESIK.guven_yuksek
            and gorev.bagimsiz_kaynak >= ESIK.bagimsiz_kaynak_gerekli
            and gorev.durum not in (Durum.KAPATILDI, Durum.BAYAT)
        ):
            sevkler.append(
                Sevk(
                    alici=Alici.SAHA_EKIBI,
                    konu="gorev_atama",
                    yuk=_ozet(gorev, kisisel=True),
                    gerekce=f"guven {gorev.guven} >= {ESIK.guven_yuksek}, ucgenleme saglandi",
                )
            )

        # --- Gonullu: makinenin cozemedigi belirsiz bant ---
        if ESIK.guven_alt <= gorev.guven < ESIK.guven_yuksek or gorev.celiski:
            sevkler.append(
                Sevk(
                    alici=Alici.GONULLU,
                    konu="dogrulama_talebi",
                    yuk=_ozet(gorev, kisisel=False) | {"celiski": gorev.celiski},
                    gerekce="belirsiz bant: insan dogrulamasi gerekiyor",
                )
            )

        # --- Valilik: toplulastirilmis tablo, kisisel veri yok ---
        sevkler.append(
            Sevk(
                alici=Alici.VALILIK,
                konu="durum_tablosu",
                yuk={
                    "ilce": gorev.konum.ilce,
                    "oncelik": gorev.oncelik,
                    "durum": gorev.durum.value,
                },
                gerekce="ilce bazli kapasite planlamasi",
            )
        )

        # --- Saglik: kirilgan grup veya canlilik isareti ---
        if any(c.kirilgan for c in gorev.cagrilar) or any(c.ses_var for c in gorev.cagrilar):
            sevkler.append(
                Sevk(
                    alici=Alici.SAGLIK,
                    konu="tibbi_hazirlik",
                    yuk=_ozet(gorev, kisisel=True),
                    gerekce="kirilgan grup veya canlilik isareti bildirildi",
                )
            )

        # --- Vatandas: kendi cagrisinin durumu ---
        sevkler.append(
            Sevk(
                alici=Alici.VATANDAS,
                konu="durum_bildirimi",
                yuk={
                    "gorev_id": gorev.id,
                    "durum": gorev.durum.value,
                    "hedef_hesaplar": sorted({c.mesaj.hesap.id for c in gorev.cagrilar}),
                },
                gerekce="cagri sahibi kendi kaydinin durumunu gorur",
            )
        )

        # --- Kamu: yalnizca dogrulanmis, yalnizca toplulastirilmis ---
        if gorev.durum is Durum.DOGRULANDI:
            sevkler.append(
                Sevk(
                    alici=Alici.KAMU,
                    konu="harita",
                    yuk={
                        "mahalle": gorev.konum.mahalle,
                        "ilce": gorev.konum.ilce,
                        "durum": gorev.durum.value,
                    },
                    gerekce="kamu haritasi mahalle duzeyinde toplulastirilir",
                )
            )
        return sevkler

    def iddia_sevkleri(self, iddia: Iddia) -> list[Sevk]:
        sevkler: list[Sevk] = []

        if iddia.yetkili:
            sevkler.append(
                Sevk(
                    alici=Alici.TEKNIK_KURUM,
                    konu="dogrulama_talebi",
                    yuk={
                        "iddia_id": iddia.id,
                        "tur": iddia.tur.value,
                        "metin": iddia.mesaj.metin[:280],
                        "yetkili": iddia.yetkili,
                        "sure_sn": ESIK.yetkili_yanit_sn,
                    },
                    gerekce=f"{iddia.tur.value} alaninin yetkilisi {iddia.yetkili}",
                )
            )

        if iddia.kesici is KesiciDurum.COZULDU and iddia.sonuc:
            sevkler.append(
                Sevk(
                    alici=Alici.GORENLERE_DUZELTME,
                    konu="geri_yayilim",
                    yuk={
                        "iddia_id": iddia.id,
                        "sonuc": iddia.sonuc,
                        "kaynak": iddia.kaynak_damgasi,
                        "hedef_kisi": iddia.goren_sayisi,
                    },
                    gerekce="duzeltme, soylentinin yayildigi grafigin uzerinden gider",
                )
            )

        # Kolluga YALNIZCA cozulmus asayis iddiasi; birey duzeyinde ihbar asla.
        if iddia.tur is IddiaTuru.ASAYIS and iddia.kesici is KesiciDurum.COZULDU:
            sevkler.append(
                Sevk(
                    alici=Alici.KOLLUK,
                    konu="dogrulanmis_olay",
                    yuk={"iddia_id": iddia.id, "sonuc": iddia.sonuc},
                    gerekce="yalnizca dogrulanmis olay iletilir",
                )
            )
        return sevkler

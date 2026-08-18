"""Esikler ve isletim sabitleri.

Her sabit, plandaki bir karar kuralinin birebir karsiligidir. Tek yerde
durmalari, raporda "esikleri onceden ilan ettik" diyebilmemizi saglar.
Bir esigi degistiren kisi, degerlendirmeyi de yeniden kosmak zorundadir.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Esikler:
    # --- A hatti: guven -> aksiyon ---
    guven_yuksek: float = 0.85
    guven_alt: float = 0.50
    bagimsiz_kaynak_gerekli: int = 2

    # --- Tazelik ---
    bayatlama_dk: float = 360.0
    kapatma_sinyali_gerekli: int = 2

    # --- Tekillestirme ---
    mekan_yaricap_m: float = 120.0
    metin_benzerlik: float = 0.72
    zaman_penceresi_dk: float = 720.0

    # --- B hatti: sistemik iddia ---
    kesici_etki_esigi: float = 0.65
    kesici_azami_sn: float = 900.0
    yetkili_yanit_sn: float = 900.0
    ivme_esigi: float = 3.0

    # --- Mod gecisi: 3 sinyalden 2 tanesi ---
    mod_icin_sinyal: int = 2

    # --- Servis seviyesi hedefleri (saniye) ---
    sla_tespit: float = 5.0
    sla_etki: float = 2.0
    sla_kesici: float = 10.0
    sla_capraz_kontrol: float = 30.0
    sla_geri_yayilim: float = 60.0


ESIK = Esikler()


KIRILGAN_SOZCUKLER = (
    "bebek", "cocuk", "çocuk", "yasli", "yaşlı", "hamile", "engelli",
    "hasta", "diyaliz", "anneannem", "dedem", "nine", "bebegim", "bebeğim",
)

CANLILIK_SOZCUKLER = (
    "ses geliyor", "sesler geliyor", "ses veriyor", "konusuyor", "konuşuyor",
    "vuruyor", "bagiriyor", "bağırıyor", "nefes", "hayatta", "canli", "canlı",
)

KAPATMA_SOZCUKLER = (
    "kurtarildi", "kurtarıldı", "kurtarildilar", "kurtarıldılar", "cikarildi",
    "çıkarıldı", "ulasildi", "ulaşıldı", "hastaneye kaldirildi",
    "hastaneye kaldırıldı", "iyi haber", "saglik durumu iyi",
)

CELISKI_SOZCUKLER = (
    "boyle bir adres yok", "böyle bir adres yok", "bu adres yok", "yanlis bilgi",
    "yanlış bilgi", "asilsiz", "asılsız", "eski paylasim", "eski paylaşım",
    "bu eski", "dogru degil", "doğru değil", "teyit edilmedi",
)

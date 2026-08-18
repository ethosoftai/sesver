"""AYIKLA - akistaki her mesaji dogru hatta gonderir.

Tasarim karari: bu asama yuksek ANMA (recall) icin ayarlidir. Bir yardim
cagrisini gurultu sanmak geri donusu olmayan bir hatadir; gurultuyu cagri
sanmak yalnizca kuyruga bir satir ekler. Bu yuzden esikler kasitli olarak
cagri lehine egiktir ve karasiz kalan her mesaj CAGRI kabul edilir.

Kural tabanli hat, model olmadan da calisir; bu sayede repo klonlanir
klonlanmaz uctan uca kosulabilir. Egitilmis model geldiginde ayni arayuzu
(ModelTriyaj) uygular, cagiran kod degismez.
"""

from __future__ import annotations

from typing import Protocol

from ..metin import icerir, kac_tane, normalize
from ..schemas import Mesaj, Tur

# Enkaz altindan gelen cagrinin cekirdek isaretleri.
CAGRI_GUCLU = (
    "enkaz altinda", "enkaz altındayız", "enkaz altindayiz", "gockuk altinda",
    "göçük altında", "mahsur", "kurtarin", "kurtarın", "yardim edin",
    "yardım edin", "cikaramiyoruz", "çıkaramıyoruz", "altinda kaldi",
    "altında kaldı", "ulasilamiyor", "ulaşılamıyor", "kurtarma ekibi lazim",
)

CAGRI_ZAYIF = (
    "acil", "imdat", "yardim", "yardım", "bina", "apartman", "kat",
    "adres", "aile", "ses geliyor", "haber alamiyoruz", "haber alamıyoruz",
)

# Sistemik iddia: tek bir binayi degil, bir bolgeyi/sistemi ilgilendiren sav.
IDDIA_NESNE = (
    "baraj", "borsa", "kopru", "köprü", "otoyol", "havalimani", "havalimanı",
    "elektrik", "dogalgaz", "doğalgaz", "sebeke", "şebeke", "hastane",
    "tsunami", "artci", "artçı", "fay", "salgin", "salgın", "su kaynagi",
)

IDDIA_FIIL = (
    "patladi", "patladı", "coktu", "çöktü", "yikildi", "yıkıldı", "kapandi",
    "kapandı", "kesildi", "tasti", "taştı", "bosaldi", "boşaldı", "sizinti",
    "sızıntı", "iflas", "durduruldu",
)

# Panik eylemi tetikleyen emir kipleri - B hattinda etki skorunu yukseltir.
EYLEM_EMRI = (
    "kacin", "kaçın", "cikin", "çıkın", "uzaklasin", "uzaklaşın", "toplanin",
    "toplanın", "gitmeyin", "yaklasmayin", "yaklaşmayın", "cekin paranizi",
    "çekin paranızı", "yuksek yere", "yüksek yere", "tahliye",
)

DESTEK = (
    "yardim edebilirim", "yardım edebilirim", "battaniye var", "kamyonet",
    "jenerator", "jeneratör", "yer acabilirim", "yer açabilirim", "gonulluyum",
    "gönüllüyüm", "malzeme gonderiyoruz", "malzeme gönderiyoruz", "asci",
    "kan verebilirim", "arac tahsis",
)

GURULTU = (
    "gecmis olsun", "geçmiş olsun", "rabbim yardimcisi", "rabbim yardımcısı",
    "dua ediyoruz", "basimiz sagolsun", "başımız sağolsun", "allah kurtarsin",
    "allah kurtarsın", "paylasin duyulsun", "paylaşın duyulsun",
    "haberi paylastim", "haberi paylaştım",
)


class Triyajci(Protocol):
    """Kural tabanli ve model tabanli hatlarin ortak arayuzu."""

    def __call__(self, mesaj: Mesaj) -> tuple[Tur, float]: ...


class KuralTriyaj:
    """Sifir bagimlilikli taban cizgisi.

    Skor ne kadar yuksekse mesajin o sinifa ait olma kanaati o kadar guclu.
    Cagri sinifina kasitli bir avantaj (bkz. ``cagri_egimi``) verilir.
    """

    def __init__(self, cagri_egimi: float = 0.6) -> None:
        self.cagri_egimi = cagri_egimi

    def __call__(self, mesaj: Mesaj) -> tuple[Tur, float]:
        m = mesaj.metin
        skor: dict[Tur, float] = {
            Tur.CAGRI: 2.5 * kac_tane(m, CAGRI_GUCLU) + 0.35 * kac_tane(m, CAGRI_ZAYIF),
            Tur.IDDIA: 0.0,
            Tur.DESTEK: 1.6 * kac_tane(m, DESTEK),
            Tur.GURULTU: 1.2 * kac_tane(m, GURULTU),
        }

        # Sistemik iddia icin nesne ve fiilin BIRLIKTE gecmesi aranir:
        # "baraj" tek basina haber, "baraj patladi" iddiadir.
        nesne = kac_tane(m, IDDIA_NESNE)
        fiil = kac_tane(m, IDDIA_FIIL)
        if nesne and fiil:
            skor[Tur.IDDIA] = 2.0 + 0.5 * (nesne + fiil)
            if icerir(m, EYLEM_EMRI):
                skor[Tur.IDDIA] += 1.5

        # Adres benzeri bir kalip cagri olasiligini yukseltir.
        n = normalize(m)
        if " mah " in f" {n} " or "mahalle" in n or "sokak" in n or "apartman" in n:
            skor[Tur.CAGRI] += 0.8

        skor[Tur.CAGRI] += self.cagri_egimi

        tur = max(skor, key=lambda k: skor[k])
        toplam = sum(v for v in skor.values() if v > 0) or 1.0
        return tur, round(min(skor[tur] / toplam, 1.0), 3)


class ModelTriyaj:
    """Egitilmis GOZCU modeli icin sarmalayici.

    Model yuklenemezse sessizce kural hattina duser. Afet sisteminde
    "model yok" bir hata degil, bir calisma kipidir (fail-open).
    """

    def __init__(self, yukleyici=None, yedek: Triyajci | None = None) -> None:
        self._model = None
        self._yedek = yedek or KuralTriyaj()
        if yukleyici is not None:
            try:
                self._model = yukleyici()
            except Exception:  # pragma: no cover - model yoklugu beklenen hal
                self._model = None

    @property
    def model_aktif(self) -> bool:
        return self._model is not None

    def __call__(self, mesaj: Mesaj) -> tuple[Tur, float]:
        if self._model is None:
            return self._yedek(mesaj)
        etiket, guven = self._model.predict(mesaj.metin)
        return Tur(etiket), float(guven)

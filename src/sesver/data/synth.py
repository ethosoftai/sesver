"""Sentetik afet akisi ureteci - yer gercekli.

Neden sentetik?
---------------
Gercek afet mesajlari kisisel veri tasir: isim, telefon, tam adres, saglik
durumu. Bir yarisma reposunda bunlari yayinlamak hem KVKK acisindan hem etik
acidan savunulamaz. Bu yuzden EGITIM ve KOSUM verisi sentetiktir; olculen
sonuclarin gercekligi ise elle etiketlenmis kucuk bir altin set uzerinde
dogrulanir (bkz. docs/veri-model-etik.md).

Uretecin degeri, YER GERCEGINI birlikte uretmesidir: her mesajin hangi olaya
ait oldugu, gercek mi sahte mi, bayat mi taze oldugu bilinir. Tekillestirme
orani, sahte bastirma ve bayat kapatma metrikleri ancak boyle olculebilir.

Uretilen dagilim, kriz bilisimi yazininin bildirdigi orana yakin tutulmustur:
akisin buyuk cogunlugu dogrudan eyleme donusturulemeyen icerik, kucuk bir
azinligi gercek yardim cagrisidir.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..schemas import Hesap, Mesaj
from .gazetteer import varsayilan_gazetteer
from .gurultu import boz

BINA_ADLARI = (
    "yilmaz", "gunes", "cinar", "ege", "sedef", "umut", "meltem", "safak",
    "dogus", "pinar", "akdeniz", "zeytin",
)

CAGRI_KALIPLARI = (
    "{yer} {sokak}. sokak {bina} apartmani {kat}. kat enkaz altindayiz {kisi} kisiyiz",
    "ACIL {yer} {sokak} sok {bina} apt {kat}.kat {kisi} kisi mahsur kaldik yardim edin",
    "{yer} {sokak}. sokak {bina} sitesi {kat}. katta {kisi} kisiyiz ses geliyor kurtarin",
    "yardim {yer} {sokak}. sok {bina} apartmani coktu {kisi} kisi iceride",
    "{yer} {sokak}. sokak {bina} apt {kat}. kat annem ve babam enkaz altinda ulasamiyoruz",
)

KIRILGAN_EK = (
    " icerde 2 cocuk var", " yasli teyzem var", " hamile ablam iceride",
    " bebek var lutfen", " dedem seker hastasi",
)

GURULTU_KALIPLARI = (
    "gecmis olsun rabbim yardimcimiz olsun",
    "dua ediyoruz herkes icin",
    "paylasin duyulsun lutfen herkes gorsun",
    "haberi paylastim umarim ulasir",
    "allah kurtarsin insallah",
    "bu saatte hala haber yok cok uzuldum",
    "tv de son dakika gecti izliyor musunuz",
)

DESTEK_KALIPLARI = (
    "elimde {n} battaniye var yardim edebilirim",
    "kamyonetim var malzeme tasiyabilirim gonulluyum",
    "jenerator gonderiyoruz {yer} tarafina",
    "kan verebilirim {yer} hastanesindeyim",
)

SAHTE_KALIPLARI = (
    "{sahte_yer} mah {sokak}. sokak {bina} apartmani {kat}. kat {kisi} kisi enkaz altinda ACIL PAYLASIN",
    "ACIL YARDIM {sahte_yer} mah {sokak}. sok {bina} apt cok acil herkes paylassin",
)

IDDIA_KALIPLARI = (
    ("baraj patladi herkes yuksek yere kacsin", False),
    ("borsa coktu paranizi cekin bankalar batiyor", False),
    ("dogalgaz hatti patladi sehri terk edin", False),
    ("yeni artci geliyor binalardan cikin", False),
    ("elektrikler kesildi bolgede sebeke coktu", True),
)

# Sinirda duran ornekler. Gercek akisin en zor kismi burasidir ve
# bunlar olmadan olculen basari yaniltici derecede yuksek cikar.
#   - baskasinin cagrisini aktaran mesaj: cagri gibi gorunur, ihbar degildir
#   - adressiz endise: ihbardir ama eyleme donusturulemez
#   - dogrulama sorusu: gurultudur ama cagri sozcukleri tasir
SINIRDA = (
    ("bir arkadasimin ailesi enkaz altinda diye paylasiyorlar lutfen duyurun", "gurultu"),
    ("bu adresi paylasiyorum kendim gormedim dogrulayan var mi", "gurultu"),
    ("su adrese ekip gitsin diyorlar teyit eden var mi acaba", "gurultu"),
    ("listede gordugum adresleri paylasiyorum sorumluluk kabul etmiyorum", "gurultu"),
    ("annemden haber alamiyoruz cok endiseliyiz nerede bilmiyoruz", "cagri"),
    ("ablam o bolgede oturuyordu telefonu kapali ulasamiyoruz", "cagri"),
    ("kardesim sabahtan beri aranmiyor lutfen bir bakan olsun", "cagri"),
    ("elimizde malzeme var ama nereye goturecegimizi bilmiyoruz", "destek"),
    ("ekip olarak yola ciktik koordinat bekliyoruz", "destek"),
)

TEYIT_YANIT = ("ben de gordum komsusuyum", "ayni binada akrabam var teyit ettim", "oradayim dogru")
YALAN_YANIT = ("boyle bir adres yok arkadaslar", "bu eski paylasim", "asilsiz bilgi yaymayin")
COZULDU_YANIT = ("kurtarildilar cok sukur", "cikarildi hepsi saglikli", "ulasildi iyi haber")


@dataclass(slots=True)
class Olay:
    """Yer gercegi: sahada gercekten olan (veya olmayan) tek olay."""

    id: str
    yer: str
    sokak: int
    bina: str
    kat: int
    kisi: int
    gercek: bool          # sahte kampanya mi
    cozuldu: bool         # kurtarildilar mi (bayatlama testi icin)
    mesaj_idleri: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Akis:
    mesajlar: list[Mesaj]
    olaylar: dict[str, Olay]
    mesaj_olay: dict[str, str]        # mesaj id -> olay id
    sahte_mesajlar: set[str]
    iddia_mesajlari: dict[str, bool]  # mesaj id -> iddia dogru mu
    mesaj_sinifi: dict[str, str]      # mesaj id -> cagri/iddia/destek/gurultu

    @property
    def gercek_olay_sayisi(self) -> int:
        return sum(1 for o in self.olaylar.values() if o.gercek)


class AkisUreteci:
    """Yer gercekli sentetik afet akisi.

    Args:
        sahte_orani: uretilen olaylarin ne kadarinin sahte kampanya olacagi
        kopya_lambda: gercek bir cagrinin ortalama kac kez yeniden paylasilacagi
    """

    def __init__(
        self,
        seed: int = 42,
        sahte_orani: float = 0.06,
        kopya_lambda: float = 6.0,
        gurultu_siddeti: float = 1.0,
        sinirda_orani: float = 0.05,
        sablon_yarisi: str | None = None,
    ) -> None:
        self.rnd = random.Random(seed)
        self.sahte_orani = sahte_orani
        self.kopya_lambda = kopya_lambda
        # Yazim bozulmasi ve sinirda ornekler: degerlendirmenin yapay olarak
        # kolaylasmasini engeller. 0 verilirse temiz sablon ciktisi uretilir.
        self.gurultu_siddeti = gurultu_siddeti
        self.sinirda_orani = sinirda_orani

        # SABLON AYRIKLIGI - modelin genellemesini olcmenin tek durust yolu.
        #
        # Tum sablonlar hem egitimde hem testte kullanilirsa model sablon
        # parmak izini ezberler ve mukemmele yakin skor uretir; bu skor
        # gercek dunyada hicbir seyi ongormez. "a" ve "b" yarilari ayrik
        # sablon kumeleri dondurur: "a" ile egitilen model, "b" testinde
        # DAHA ONCE HIC GORMEDIGI ifade bicimleriyle karsilasir.
        self.sablon_yarisi = sablon_yarisi
        self.g = varsayilan_gazetteer()
        self._mahalleler = self.g.mahalleler

        self._cagri_kalip = self._dilim(CAGRI_KALIPLARI)
        self._gurultu_kalip = self._dilim(GURULTU_KALIPLARI)
        self._destek_kalip = self._dilim(DESTEK_KALIPLARI)
        self._iddia_kalip = self._dilim(IDDIA_KALIPLARI)
        self._sinirda = self._dilim(SINIRDA)

    def _dilim(self, havuz):
        """Sablon havuzunun istenen yarisi. None ise tamami."""
        if self.sablon_yarisi is None:
            return list(havuz)
        kalan = 0 if self.sablon_yarisi == "a" else 1
        secim = [x for i, x in enumerate(havuz) if i % 2 == kalan]
        return secim or list(havuz)

    def uret(self, mesaj_sayisi: int = 2000, saat: float = 12.0) -> Akis:
        mesajlar: list[Mesaj] = []
        olaylar: dict[str, Olay] = {}
        mesaj_olay: dict[str, str] = {}
        sahte: set[str] = set()
        iddialar: dict[str, bool] = {}
        sinif: dict[str, str] = {}   # triyaj egitimi icin yer gercegi

        sure = saat * 3600.0
        t0 = 1_000_000.0
        sayac = 0

        def yeni_id() -> str:
            nonlocal sayac
            sayac += 1
            return f"M-{sayac:07d}"

        while len(mesajlar) < mesaj_sayisi:
            zar = self.rnd.random()
            ts = t0 + self.rnd.random() * sure

            # --- %8 gercek yardim cagrisi (ve kopyalari) ---
            if zar < 0.08:
                olay = self._olay_uret(f"O-{len(olaylar) + 1:05d}")
                olaylar[olay.id] = olay
                kopya = 1 + int(self.rnd.expovariate(1 / self.kopya_lambda))
                for k in range(kopya):
                    if len(mesajlar) >= mesaj_sayisi:
                        break
                    mid = yeni_id()
                    metin = self._cagri_metni(olay, varyant=k)
                    hesap = self._hesap(olay.gercek, ilk=(k == 0))
                    m = Mesaj(
                        id=mid,
                        metin=metin,
                        hesap=hesap,
                        ts=ts + k * self.rnd.uniform(30, 900),
                        paylasim=self.rnd.randint(0, 400),
                    )
                    mesajlar.append(m)
                    mesaj_olay[mid] = olay.id
                    sinif[mid] = "cagri"
                    olay.mesaj_idleri.append(mid)
                    if not olay.gercek:
                        sahte.add(mid)

                # Yanit zinciri: teyit / yalanlama / cozulme
                self._yanitlar(olay, mesajlar, mesaj_sayisi, yeni_id, ts)

            # --- %4 sistemik iddia ---
            elif zar < 0.12:
                metin, dogru = self.rnd.choice(self._iddia_kalip)
                mid = yeni_id()
                mesajlar.append(
                    Mesaj(
                        id=mid,
                        metin=metin,
                        hesap=self._hesap(True, ilk=True),
                        ts=ts,
                        paylasim=self.rnd.randint(200, 5000),
                    )
                )
                iddialar[mid] = dogru
                sinif[mid] = "iddia"

            # --- sinirda duran ornekler ---
            elif zar < 0.12 + self.sinirda_orani:
                metin, gercek_sinif = self.rnd.choice(self._sinirda)
                mid = yeni_id()
                mesajlar.append(
                    Mesaj(
                        id=mid,
                        metin=metin,
                        hesap=self._hesap(True, ilk=True),
                        ts=ts,
                        paylasim=self.rnd.randint(0, 300),
                    )
                )
                sinif[mid] = gercek_sinif

            # --- %10 destek teklifi ---
            elif zar < 0.22 + self.sinirda_orani:
                mid = yeni_id()
                kalip = self.rnd.choice(self._destek_kalip)
                mesajlar.append(
                    Mesaj(
                        id=mid,
                        metin=kalip.format(
                            n=self.rnd.randint(10, 500), yer=self.rnd.choice(self._mahalleler)
                        ),
                        hesap=self._hesap(True, ilk=True),
                        ts=ts,
                    )
                )

                sinif[mid] = "destek"

            # --- kalan: gurultu ---
            else:
                mid = yeni_id()
                mesajlar.append(
                    Mesaj(
                        id=mid,
                        metin=self.rnd.choice(self._gurultu_kalip),
                        hesap=self._hesap(True, ilk=True),
                        ts=ts,
                        paylasim=self.rnd.randint(0, 50),
                    )
                )
                sinif[mid] = "gurultu"

        # Yazim bozulmasi tum mesajlara uygulanir. Etiketler bozulmus metne
        # gore turetildigi icin veri kumesi tutarli kalir.
        if self.gurultu_siddeti > 0:
            for m in mesajlar:
                m.metin = boz(m.metin, self.rnd, self.gurultu_siddeti)

        mesajlar.sort(key=lambda m: m.ts)
        return Akis(
            mesajlar=mesajlar[:mesaj_sayisi],
            olaylar=olaylar,
            mesaj_olay=mesaj_olay,
            sahte_mesajlar=sahte,
            iddia_mesajlari=iddialar,
            mesaj_sinifi=sinif,
        )

    # --- ic yardimcilar ---

    def _olay_uret(self, oid: str) -> Olay:
        gercek = self.rnd.random() > self.sahte_orani
        return Olay(
            id=oid,
            yer=self.rnd.choice(self._mahalleler),
            sokak=self.rnd.randint(1, 120),
            bina=self.rnd.choice(BINA_ADLARI),
            kat=self.rnd.randint(1, 8),
            kisi=self.rnd.randint(1, 9),
            gercek=gercek,
            cozuldu=gercek and self.rnd.random() < 0.30,
        )

    def _cagri_metni(self, olay: Olay, varyant: int) -> str:
        if not olay.gercek:
            kalip = self.rnd.choice(SAHTE_KALIPLARI)
            # Sahte kampanya sozlukte olmayan bir yer adi kullanir.
            return kalip.format(
                sahte_yer=f"{olay.bina}kent",
                sokak=olay.sokak,
                bina=olay.bina,
                kat=olay.kat,
                kisi=olay.kisi,
            )
        kalip = self._cagri_kalip[varyant % len(self._cagri_kalip)]
        metin = kalip.format(
            yer=f"{olay.yer} mah",
            sokak=olay.sokak,
            bina=olay.bina,
            kat=olay.kat,
            kisi=olay.kisi,
        )
        if self.rnd.random() < 0.35:
            metin += self.rnd.choice(KIRILGAN_EK)
        return metin

    def _hesap(self, gercek: bool, ilk: bool) -> Hesap:
        if not gercek and ilk:
            # Sahte kampanyanin imzasi: yeni acilmis, bolgeyle gecmisi olmayan hesap.
            return Hesap(
                id=f"yeni{self.rnd.randint(1, 99999)}",
                yas_gun=self.rnd.randint(0, 5),
                takipci=self.rnd.randint(0, 40),
                bolgede_gecmis=False,
            )
        return Hesap(
            id=f"h{self.rnd.randint(1, 40000)}",
            yas_gun=self.rnd.randint(60, 3000),
            takipci=self.rnd.randint(10, 8000),
            bolgede_gecmis=self.rnd.random() < 0.7,
        )

    def _yanitlar(self, olay, mesajlar, limit, yeni_id, ts) -> None:
        if not olay.mesaj_idleri or len(mesajlar) >= limit:
            return
        kok = olay.mesaj_idleri[0]

        if olay.gercek and self.rnd.random() < 0.45:
            mesajlar.append(
                Mesaj(
                    id=yeni_id(),
                    metin=self.rnd.choice(TEYIT_YANIT),
                    hesap=self._hesap(True, ilk=True),
                    ts=ts + self.rnd.uniform(60, 1800),
                    yanit_verilen=kok,
                )
            )
        if not olay.gercek and self.rnd.random() < 0.55:
            mesajlar.append(
                Mesaj(
                    id=yeni_id(),
                    metin=self.rnd.choice(YALAN_YANIT),
                    hesap=self._hesap(True, ilk=True),
                    ts=ts + self.rnd.uniform(120, 3600),
                    yanit_verilen=kok,
                )
            )
        if olay.cozuldu:
            for _ in range(2):
                mesajlar.append(
                    Mesaj(
                        id=yeni_id(),
                        metin=self.rnd.choice(COZULDU_YANIT),
                        hesap=self._hesap(True, ilk=True),
                        ts=ts + self.rnd.uniform(1800, 9000),
                        yanit_verilen=kok,
                    )
                )

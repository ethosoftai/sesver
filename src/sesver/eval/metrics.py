"""Metrik tanimlari.

Her metrik, sistemin gercekten cozdugunu iddia ettigi bir problemin
olculebilir karsiligidir. Iddia edilmeyen sey olculmez; olculmeyen sey
raporda yazilmaz.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class TriyajMetrik:
    """Yardim cagrisini kacirmak geri donusu olmayan hatadir: ANMA one cikar."""

    anma: float           # gercek cagrilarin kaci CAGRI olarak siniflandi
    kesinlik: float       # CAGRI denenlerin kaci gercekten cagri
    f1: float
    kacan: int            # kacirilan gercek cagri sayisi - hedef: 0


@dataclass(slots=True)
class TekillestirmeMetrik:
    """Hacim problemi: kac mesaj kac goreve indi, ve karistirmadan mi?"""

    cagri: int
    gorev: int
    oran: float              # cagri / gorev
    saflik: float            # tek yer-gercegi olayindan olusan gorev orani
    kapsama: float           # yer gercegindeki olaylarin kaci yakalandi
    konumsuz: int            # adres cozulemeyen, gonullu havuzuna dusen


@dataclass(slots=True)
class BastirmaMetrik:
    """Sahte kayitlar kuyrukta ne kadar asagi itiliyor?

    Silme yok, sadece sıralama. Basari olcutu: sahte kayitlarin ust siralarda
    gorunmemesi, gercek kayitlarin ise ASLA elenmemesi.
    """

    sahte_gorev: int
    sahte_ilk_100: int          # sahtelerden kaci ilk 100'e girdi
    sahte_medyan_yuzdelik: float  # 1.0 = kuyrugun en dibi
    gercek_kaybi: int             # kuyruktan tamamen dusen gercek gorev - hedef: 0


@dataclass(slots=True)
class TazelikMetrik:
    cozulmus_olay: int
    kapatilan: int
    kapatma_orani: float


@dataclass(slots=True)
class HizMetrik:
    mesaj: int
    sure_sn: float
    mesaj_sn: float
    asama_sn: dict[str, float]


@dataclass(slots=True)
class Rapor:
    triyaj: TriyajMetrik
    tekillestirme: TekillestirmeMetrik
    bastirma: BastirmaMetrik
    tazelik: TazelikMetrik
    hiz: HizMetrik
    kesici_acilan: int
    kesici_cozulen: int

    def sozluk(self) -> dict:
        return asdict(self)

    def yazdir(self) -> str:
        t, d, b, z, h = (
            self.triyaj,
            self.tekillestirme,
            self.bastirma,
            self.tazelik,
            self.hiz,
        )
        satir = [
            "",
            "=" * 66,
            "  SES VER-Bench",
            "=" * 66,
            "",
            "  TRIYAJ (yardim cagrisini kacirmamak)",
            f"    anma            {t.anma:.4f}   <- kritik metrik",
            f"    kesinlik        {t.kesinlik:.4f}",
            f"    F1              {t.f1:.4f}",
            f"    kacan cagri     {t.kacan}          <- hedef 0",
            "",
            "  TEKILLESTIRME (hacim problemi)",
            f"    cagri           {d.cagri}",
            f"    gorev           {d.gorev}",
            f"    indirgeme       {d.oran:.1f}x",
            f"    kume safligi    {d.saflik:.4f}   <- 1.0 = hicbir olay karismadi",
            f"    olay kapsamasi  {d.kapsama:.4f}",
            f"    konumsuz havuz  {d.konumsuz}        (gonullu adres zenginlestirmesi)",
            "",
            "  BASTIRMA (sahteyi silmeden asagi itmek)",
            f"    sahte gorev     {b.sahte_gorev}",
            f"    ilk 100'de      {b.sahte_ilk_100}",
            f"    medyan yuzdelik {b.sahte_medyan_yuzdelik:.3f}   <- 1.0 = kuyrugun dibi",
            f"    kaybolan gercek {b.gercek_kaybi}          <- hedef 0",
            "",
            "  TAZELIK (bayat kaydi kapatmak)",
            f"    cozulmus olay   {z.cozulmus_olay}",
            f"    kapatilan       {z.kapatilan}",
            f"    kapatma orani   {z.kapatma_orani:.4f}",
            "",
            "  B HATTI",
            f"    kesici acilan   {self.kesici_acilan}",
            f"    kesici cozulen  {self.kesici_cozulen}",
            "",
            "  HIZ (tek cekirdek, model yok, saf Python)",
            f"    mesaj           {h.mesaj}",
            f"    sure            {h.sure_sn:.2f} sn",
            f"    verim           {h.mesaj_sn:,.0f} mesaj/sn",
        ]
        for asama, sn in sorted(h.asama_sn.items(), key=lambda x: -x[1]):
            satir.append(f"      {asama:16s} {sn:.3f} sn")
        satir += ["", "=" * 66, ""]
        return "\n".join(satir)

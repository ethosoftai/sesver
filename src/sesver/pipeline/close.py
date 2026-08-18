"""KAPAT - bayat gorevleri duserir, cozulenleri kapatir.

2023 sahasindaki en pahali hata buydu: kurtarilmis insanlarin cagrilari
gunlerce dolasmaya devam etti, ekipler bosaltilmis binalara gonderildi.
Bir afet sisteminde "kaydi acmak" kadar "kaydi kapatmak" da urun ozelligidir.

Uc kapanma yolu vardir:
  1. Sahibi kapatir      - bestecideki tek dokunusluk "kurtarildik" tusu
  2. Kalabalik kapatir   - yanit zincirinde yeterli sayida cozuldu durusu
  3. Ekip kapatir        - kurum panelinden gorev tamamlandi bildirimi

Hicbiri gelmezse gorev SILINMEZ; bayatlar. Bayat gorev kuyrukta gorunur
kalir, yalnizca en alta iner ve yeniden teyit istenir.
"""

from __future__ import annotations

from ..config import ESIK
from ..schemas import Durum, Gorev


class Kapatici:
    def __call__(self, gorev: Gorev, simdi: float) -> Gorev:
        if gorev.durum in (Durum.KAPATILDI, Durum.ASILSIZ):
            return gorev

        if gorev.kapatma_sinyali >= ESIK.kapatma_sinyali_gerekli:
            gorev.durum = Durum.KAPATILDI
            gorev.iz.append(f"kapatildi: {gorev.kapatma_sinyali} cozuldu sinyali")
            return gorev

        if gorev.yas_dk(simdi) > ESIK.bayatlama_dk and gorev.durum is not Durum.EKIP_ATANDI:
            gorev.durum = Durum.BAYAT
            gorev.iz.append(
                f"bayat: {gorev.yas_dk(simdi):.0f} dk teyitsiz, yeniden teyit istendi"
            )
        return gorev

    def sahibi_kapatti(self, gorev: Gorev, hesap_id: str) -> bool:
        """Cagriyi acan kisi kendi kaydini tek dokunusla kapatabilir."""
        sahipler = {c.mesaj.hesap.id for c in gorev.cagrilar}
        if hesap_id not in sahipler:
            return False
        gorev.durum = Durum.KAPATILDI
        gorev.iz.append("kapatildi: cagri sahibi bildirimi")
        return True

    def ekip_kapatti(self, gorev: Gorev, ekip: str) -> None:
        gorev.durum = Durum.KAPATILDI
        gorev.iz.append(f"kapatildi: {ekip} gorev tamamlandi bildirimi")

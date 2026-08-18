"""BILDIR - etiketlenen kayitlari mail ile ilgili kutuya bildirir.

Bu modul YONET katmaninin insan-onayli ucudur. Sistem hicbir zaman dogrudan
sosyal medyaya yazmaz, hicbir hesabi taklit etmez, kimseyi ikna etmeye
calismaz. Yaptigi tek sey, etiketlenmis (tespit edilmis ya da sonuclanmis)
kaydi onceden tanimli bir kutuya mail olarak dusurmektir. Yayin ya da
mudahale karari her zaman postayi okuyan insanda/kurumda kalir.

Ucuncu tetikleyici (bkz. pipeline/graph.py):
  1. IDDIA TESPIT   - devre kesici acildiginda (etki esigi asildi)
  2. IDDIA SONUC    - kesici cozuldu ya da yanitsiz dustugunde
  3. YUKSEK ONCELIK - A hattinda bir gorev ESIK.gorev_bildirim_esigi'ni
                       gectiginde, gorev basina yalnizca bir kez

DURUSTLUK NOTU
--------------
Varsayilan olarak KAPALIDIR (``SESVER_MAIL_ENABLED=1`` ile acilir); demo ve
testler hicbir ag istegi atmaz. Gonderim basarisiz olursa boru hatti susmaz
(fail-open): hata ``Bildirimci.gunluk``e yazilir, akis devam eder.
"""

from __future__ import annotations

import os
import smtplib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage

from .claims.registry import yetkili_bul
from .config import ESIK
from .schemas import Gorev, Iddia, KesiciDurum


@dataclass(frozen=True, slots=True)
class MailAyarlari:
    etkin: bool = False
    host: str = "localhost"
    port: int = 25
    kullanici: str | None = None
    parola: str | None = None
    tls: bool = False
    gonderen: str = "sesver@ornek.local"
    varsayilan_alici: str = "afad-koordinasyon@ornek.gov.tr"


def ortam_ayarlari() -> MailAyarlari:
    """Ortam degiskenlerinden SMTP ayarlarini okur; hicbiri yoksa devre disi kalir."""
    return MailAyarlari(
        etkin=os.environ.get("SESVER_MAIL_ENABLED", "0") == "1",
        host=os.environ.get("SESVER_SMTP_HOST", "localhost"),
        port=int(os.environ.get("SESVER_SMTP_PORT", "25")),
        kullanici=os.environ.get("SESVER_SMTP_USER") or None,
        parola=os.environ.get("SESVER_SMTP_PASS") or None,
        tls=os.environ.get("SESVER_SMTP_TLS", "0") == "1",
        gonderen=os.environ.get("SESVER_MAIL_FROM", "sesver@ornek.local"),
        varsayilan_alici=os.environ.get("SESVER_ALERT_EMAIL", "afad-koordinasyon@ornek.gov.tr"),
    )


def _smtp_gonder(ayar: MailAyarlari, alici: str, konu: str, govde: str) -> None:
    msg = EmailMessage()
    msg["From"] = ayar.gonderen
    msg["To"] = alici
    msg["Subject"] = konu
    msg.set_content(govde)

    with smtplib.SMTP(ayar.host, ayar.port, timeout=10) as sunucu:
        if ayar.tls:
            sunucu.starttls()
        if ayar.kullanici and ayar.parola:
            sunucu.login(ayar.kullanici, ayar.parola)
        sunucu.send_message(msg)


@dataclass(slots=True)
class BildirimKaydi:
    """Gonderilen ya da basarisiz olan her mailin izi (denetlenebilirlik)."""

    alici: str
    konu: str
    ts: float
    basarili: bool
    hata: str | None = None


@dataclass(slots=True)
class Bildirimci:
    """Etiketlenmis kayitlari mail ile bildirir. Hicbir zaman platforma yazmaz."""

    ayar: MailAyarlari = field(default_factory=ortam_ayarlari)
    gonderici: Callable[[MailAyarlari, str, str, str], None] = _smtp_gonder
    gunluk: list[BildirimKaydi] = field(default_factory=list)
    _bildirilen_gorevler: set[str] = field(default_factory=set)

    def _gonder(self, alici: str, konu: str, govde: str) -> bool:
        if not alici:
            alici = self.ayar.varsayilan_alici
        if not self.ayar.etkin:
            self.gunluk.append(
                BildirimKaydi(alici, konu, time.time(), False, "mail devre disi")
            )
            return False
        try:
            self.gonderici(self.ayar, alici, konu, govde)
        except Exception as exc:  # fail-open: mail cikmazi hatti durdurmaz
            self.gunluk.append(BildirimKaydi(alici, konu, time.time(), False, str(exc)))
            return False
        self.gunluk.append(BildirimKaydi(alici, konu, time.time(), True))
        return True

    # --- B hatti ---

    def iddia_tespit_edildi(self, iddia: Iddia) -> bool:
        """Devre kesici acildiginda cagrilir: yetkiliye erken alarm."""
        kayit = yetkili_bul(iddia.tur)
        konu = f"[SES VER] Iddia tespit edildi: {iddia.tur.value} (etki={iddia.etki:.2f})"
        govde = (
            f"Iddia ID: {iddia.id}\n"
            f"Tur: {iddia.tur.value}\n"
            f"Etki skoru: {iddia.etki:.2f}\n"
            f"Metin: {iddia.mesaj.metin[:500]}\n"
            f"Kesici durumu: {iddia.kesici.value}\n"
            f"Yetkili: {iddia.yetkili or '-'}\n"
        )
        return self._gonder(kayit.mail, konu, govde)

    def iddia_sonuclandi(self, iddia: Iddia) -> bool:
        """Kesici cozuldu ya da yanitsiz dustugunde cagrilir: kapanis bildirimi."""
        if iddia.kesici not in (KesiciDurum.COZULDU, KesiciDurum.YANITSIZ):
            return False
        kayit = yetkili_bul(iddia.tur)
        konu = f"[SES VER] Iddia sonuclandi: {iddia.tur.value} -> {iddia.kesici.value}"
        govde = (
            f"Iddia ID: {iddia.id}\n"
            f"Tur: {iddia.tur.value}\n"
            f"Sonuc: {iddia.sonuc or '-'}\n"
            f"Kaynak: {iddia.kaynak_damgasi or '-'}\n"
            f"Durum: {iddia.kesici.value}\n"
        )
        return self._gonder(kayit.mail, konu, govde)

    # --- A hatti ---

    def gorev_yuksek_oncelik(self, gorev: Gorev) -> bool:
        """Oncelik esigini gecen gorev icin, gorev basina yalnizca bir kez cagrilir."""
        if gorev.id in self._bildirilen_gorevler:
            return False
        if gorev.oncelik < ESIK.gorev_bildirim_esigi:
            return False
        self._bildirilen_gorevler.add(gorev.id)
        k = gorev.konum
        konu = f"[SES VER] Yuksek oncelikli gorev: {gorev.id} (oncelik={gorev.oncelik:.2f})"
        govde = (
            f"Gorev ID: {gorev.id}\n"
            f"Oncelik: {gorev.oncelik:.3f}\n"
            f"Guven: {gorev.guven:.2f}\n"
            f"Bagimsiz kaynak: {gorev.bagimsiz_kaynak}\n"
            f"Adres: {k.ilce or '?'} / {k.mahalle or '?'} / {k.sokak or '-'} / {k.bina or '-'}\n"
            f"Durum: {gorev.durum.value}\n"
        )
        return self._gonder(self.ayar.varsayilan_alici, konu, govde)

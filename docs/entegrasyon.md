# SES VER × NSosyal — Entegrasyon ve İşletim Planı

## 1. Sınır çizgisi — kim neyi veriyor

**NSosyal'in verdiği (mevcut altyapı):** olay akışı (gönderi/yanıt/paylaşım event bus'ı) ·
hesap ve kimlik meta verisi · konum etiketi ve medya deposu · bildirim servisi ·
akış sıralama servisi (biz sinyal veririz, o uygular).

**SES VER'in verdiği (yeni katman):** anlama (iddia/çağrı ayrımı, alan çıkarımı,
konumlandırma) · karar (tekilleştirme, doğrulama skoru, öncelik) · yönlendirme
(kime ne gidecek) · geri besleme (durum, kapatma, düzeltme yayılımı).

SES VER **ayrı bir servis**. Monolitin içine girmiyor, olay veriyoluna abone oluyor.
Üç faydası: NSosyal'e dokunmadan geliştirilebilir · çöktüğünde platform çökmez ·
başka platforma/kuruma da takılabilir (yaygın etki argümanı).

## 2. Ürün yüzeyleri — NSosyal'de tam olarak nerede görünüyor

| # | Yüzey | Kime | Ne zaman görünür |
|---|---|---|---|
| 1 | Afet Modu durum çubuğu (üst bar) | Herkes | Mod açılınca |
| 2 | Yardım Çağrısı bestecisi (yapılandırılmış form) | Afet bölgesindeki kullanıcı | Mod açılınca, tek dokunuş |
| 3 | Doğrulanmış Harita sekmesi | Herkes | T+1 saat |
| 4 | Gönderi durum rozeti (doğrulanıyor/doğrulandı/bayat/kapatıldı) | Herkes | Mod açılınca |
| 5 | "Kurtarıldık" kapatma tuşu | Çağrı sahibi + iş parçacığı | Çağrı oluşunca |
| 6 | Ön-aşılama kartları | Bölge dışı kullanıcılar | T+2 dakika |
| 7 | Devre kesici sürtünmesi | Paylaşmaya çalışan kişi | Eşik aşılınca |
| 8 | Kurum paneli (ayrı web) | AFAD, valilik, teknik kurumlar | Mod açılınca |
| 9 | Gönüllü doğrulama paneli | Eğitimli gönüllüler | Mod açılınca |

## 3. AI neyi izliyor — sinyal envanteri

### A. Platform içi (birincil, sürekli)
| Sinyal | Ne için | Frekans |
|---|---|---|
| Yeni gönderi metni + medya | Çağrı/iddia tespiti, alan çıkarımı | Akış (sürekli) |
| **Yanıt zincirleri** | Duruş analizi — "kurtarıldılar", "bu adres yok" | Akış |
| Paylaşım/alıntı grafiği | Yayılım hızı ve **ivmesi** | 10 sn pencere |
| Hesap meta (yaş, konum tutarlılığı, geçmiş isabet) | Güvenilirlik önceliği | Sorgu anında |
| Yapılandırılmış çağrı formları | Yüksek güvenli kanal | Akış |
| Arama sorguları + cevapsız soru hacmi | **Bilgi boşluğu tespiti** | 60 sn pencere |
| Silme/düzenleme davranışı | Geri çekilen iddia sinyali | Olay bazlı |
| Medya parmak izi | Geri dönüştürülmüş görsel tespiti | Yükleme anında |

### B. Platform dışı (doğrulama kaynakları)
AFAD + Kandilli sismik akışı · MGM · DSİ telemetri · TEİAŞ/EPDK · BOTAŞ · KGM ·
Borsa İstanbul · Sağlık Bakanlığı · resmî kurum hesapları · **UAVT ulusal adres veri
tabanı** (adres doğrulamanın belkemiği) · bina/yapı envanteri · haber ajansları.

### C. Türetilmiş sinyaller (sistemin kendi ürettiği)
Olay kümesi yoğunluğu (aynı binaya kaç **bağımsız** ihbar) · tazelik saati (her görevin
yaşı) · çelişki skoru · yayılım ivmesi (dakikalık türev — organik viralden ayırmak için) ·
**eylem tetikleme skoru** ("kaçın", "çekin", "toplanın" gibi emir kipleri) · ekip kapasite
doluluğu.

## 4. Karar eşikleri — skor neyi tetikliyor

### A hattı (yardım çağrısı)
| Güven | Aksiyon | Otomatik mi |
|---|---|---|
| ≥ 0,85 **ve** 2 bağımsız kaynak | Doğrudan görev kuyruğuna, yüksek öncelik | ✅ |
| 0,50 – 0,85 | Görev kuyruğunda "doğrulanmamış" etiketiyle + gönüllü kuyruğuna paralel | ✅ |
| < 0,50 | Sadece gönüllü kuyruğu, sıralamada aşağıda | ✅ |
| Her durumda | **Hiçbir kayıt silinmez** | — |

### B hattı (sistemik iddia)
| Koşul | Aksiyon |
|---|---|
| Etki skoru ≥ eşik **ve** doğrulama belirsiz | Devre kesici (≤ 15 dk, otomatik) |
| Yetkili veri kaynağı cevap verdi | Kartı bas + geri yayılım |
| Kurum 15 dk içinde cevap vermedi | Durum "yanıtsız" olarak kamuya görünür |
| Kesici 15 dk'yı aşacak | **İnsan onayı zorunlu** |

## 5. Yönlendirme matrisi — kime ne gidiyor

| Alıcı | Ne alır | Ne zaman | Kanal | Ne göremez |
|---|---|---|---|---|
| **AFAD koordinasyon** | Tekilleştirilmiş, konumlanmış, önceliklendirilmiş tam görev listesi | Sürekli akış + 15 dk özet | Panel + API | — (tam yetki) |
| **Saha ekibi** (AKUT/UMKE/itfaiye) | Yalnız kendi sektöründeki görevler, navigasyonlu, **çevrimdışı çalışır** | Yeni yüksek öncelikli görev düşünce anında | Mobil panel + push | Diğer sektörler |
| **Valilik / kriz masası** | Toplulaştırılmış tablo: ilçe bazlı karşılanmamış talep, kapasite açığı, **bilgi boşluğu uyarısı** | 15 dk | Panel | Kişisel veri |
| **Teknik kurum** (DSİ/TEİAŞ/BOTAŞ/KGM) | Yalnız kendi alanındaki B hattı iddiası + 15 dk sayaç | Anında | Panel + SMS/e-posta | Diğer alanlar, A hattı |
| **Sağlık (112/hastane)** | Yaralı bildirimleri, kan ihtiyacı, hastane kapasite iddiaları | Anında | Panel | Alakasız görevler |
| **Kolluk** | **Yalnız doğrulanmış** asayiş olayları + toplulaştırılmış söylenti durumu | 15 dk | Panel | **Doğrulanmamış bireysel ihbar — asla** |
| **Doğrulama gönüllüsü** | Makinenin çözemediği kuyruk, etki × belirsizlik sırasıyla | Sürekli | Panel | Tam iletişim bilgisi |
| **Çağrıyı atan vatandaş** | Kendi çağrısının durumu: alındı → eşleştirildi → ekip yolda → kapatıldı | Durum değişince | Push | Başkalarının kaydı |
| **Genel kamu** | Doğrulanmış harita (bina düzeyinde toplulaştırılmış), ön-aşılama kartları | Sürekli | Uygulama | İsim, telefon, sağlık durumu |
| **Söylentiyi görenler** | Düzeltme, **yayılım grafiğinin aynısı üzerinden** | Doğrulamadan < 60 sn | Push | — |
| **Basın / kurumsal** | Kaynak damgalı doğrulanmış akış | Sürekli | API | Kişisel veri |

## 6. Zaman çizelgesi — T+0'dan T+72 saate

| An | Olay |
|---|---|
| T+0 | Sismik sinyal (AFAD/Kandilli) |
| T+30 sn | **İZLEME** modu — hatlar ısınır, kesici henüz kapalı |
| T+2 dk | İkinci sinyal (hacim anomalisi) → **AFET MODU** otomatik açılır |
| T+2 dk | Besteci değişir · ön-aşılama kartları düşer · akış sıralaması fayda odaklıya geçer |
| T+3 dk | B hattı canlı — devre kesici devrede |
| T+5 dk | İlk görevler kuyruğa düşer |
| T+15 dk | AFAD'a ilk yapılandırılmış devir |
| T+30 dk | Gönüllü doğrulama paneli açılır |
| T+1 sa | Doğrulanmış kamu haritası yayına |
| T+6 sa | Bayat kayıt kapatma döngüsü ağırlık kazanır |
| T+24 sa | İhtiyaç profili kayar: kurtarmadan barınma/ısınma/ilaca |
| T+72 sa | **SÖNÜMLEME** — kesici kapanır, mod normale döner, arşiv kilitlenir |

## 7. Mahremiyet sınırı

Yardım çağrısı en hassas veri türlerinden birini taşıyor: isim, telefon, tam konum,
sağlık durumu.

- **Kamuya açık haritada** yalnızca bina düzeyinde toplulaştırma — kişisel bilgi yok
- **Tam kayıt** sadece yetkili kurum panelinde
- **İletişim bilgisi** yalnızca görevi üstlenen ekibe, yalnız görev süresince
- **KVKK dayanağı:** hayati menfaat istisnası — ama saklama süresi tanımlı, olay
  kapandıktan sonra anonimleştirme zorunlu
- **Kolluğa doğrulanmamış bireysel ihbar gitmez.** Bu tasarım kararı raporda açıkça
  gerekçelendirilir.

## 8. Arıza davranışı

**Fail-open.** Model çökerse sistem susmaz: sıralama ve devre kesici devre dışı kalır,
ham akış geçmeye devam eder. Afet sisteminin asla yapmaması gereken şey susmaktır.

Çevrimdışı replika: AFAD koordinasyon merkezindeki dizüstünde tam yığın çalışır,
internet olmadan. Model 1-3B, INT4 kuantize.

# SES VER

**Afet aninda sosyal medyanin gurultusunu, dakikalar icinde dogrulanmis bir kurtarma gorev listesine ceviren ajan sistemi.**

TEKNOFEST 2026 · NSosyal Inovasyon Yarismasi · Sosyal Yapay Zeka dikeyi

```bash
git clone https://github.com/ethosoftai/sesver
cd sesver
python -m sesver.cli demo        # bagimlilik gerekmez, hemen kosar
```

---

## Problem

Buyuk bir afetin ilk 72 saatinde sosyal medya, en yuksek hacimli ve en hizli
yer gercegi kaynagi haline gelir - ve operasyonel olarak kullanilamaz:

| Sorun | Sonuc |
|---|---|
| Milyonlarca mesaj icinde gercek cagri kayboluyor | Ekip nereye gidecegini bilmiyor |
| Adresler serbest metin: *"Armutlu, 5. sokak, marketin arkasi"* | Kayit haritaya dusmuyor |
| Bir ailenin cagrisi 50.000 kez paylasiliyor | Ayni bina defalarca gorev aciyor |
| **Kurtarilmis insanlarin cagrisi gunlerce dolasiyor** | **Ekipler bosaltilmis binalara gidiyor** |
| Sahte ihbar ve dezenformasyon | Kit kurtarma kapasitesi bosa harcaniyor |
| AFAD'a yapilandirilmis devir yok | 2023'te bu isi gonulluler elle yapti |

## Cozum

Iki ayri hat, cunku ekonomileri zit:

**A HATTI - yardim cagrisi.** Yuz binlerce kayit, her biri tek bir binayi
ilgilendirir. Sekiz asama: `ayikla -> coz -> yer bul -> birlestir -> dogrula
-> onceliklendir -> aktar -> kapat`

**B HATTI - sistemik iddia.** Onlarca kayit, her biri milyonlarca kisiyi
ilgilendirir. *"Baraj patladi"* bir yardim cagrisi degildir; yanlissa
kitlesel panige, dogruysa gec kalinmis bir tahliyeye yol acar.

---

## Uc tasarim karari

### 1. Kayit silinmez, siralanir

Kurtarma baglaminda maliyet asimetriktir:

- Gercek cagriyi elemek → **bir aile olur**
- Sahte cagriyi gecirmek → kit kapasite bosa gider, o kapasite baska yerde birini oldurur

Ikisi de olumcludur. Bu yuzden ikili "dogru/yanlis" siniflandirmasi yanlis
tasarimdir. Her kayit bir guven skoru alir ve oncelik kuyruguna girer; hicbir
sey yok edilmez, yalnizca asagi iner.

> Sistem neyin dogru oldugunu iddia etmiyor. **Yanlis olma maliyetini yonetiyor.**

### 2. Oncelik guvene esit degildir

```
oncelik = siddet × zaman_baskisi × √guven
```

Karekok bilincli bir secimdir: guven bir **siralama carpani**, bir **eleme
kapisi** degil. Tek kaynakli ama *"3 cocuk var, sesler geliyor"* diyen bir
cagri, iki kaynakli ama isaretsiz bir cagrinin ustunde kalir.

### 3. Sistem kahin degil, yonlendiricidir

*"Baraj patladi"* iddiasinin cevabi **su anda bir veritabaninda duruyor.**
DSI'nin o barajda telemetrisi var. Sorun bilgi eksikligi degil, **yonlendirme
gecikmesidir**: soylenti dort dakikada iki yuz bin kisiye ulasir, cevap uc
saat sonra basin aciklamasiyla gelir.

B hatti o gecikmeyi kapatir ve duzeltmeyi **soylentinin yayildigi grafigin
uzerinden** geri gonderir - yani tam olarak onu gormus kisilere.

---

## Olculen sonuclar

Sentetik akis, 20.000 mesaj, tek cekirdek, **model olmadan** (saf kural hatti).
Rakamlarin tamami `python -m sesver.cli bench` ile yeniden uretilebilir.

### Triyaj - yardim cagrisini kacirmamak
| Metrik | Deger |
|---|---|
| **Anma** | **1.0000** |
| **Kacan gercek cagri** | **0** |
| Kesinlik | 0.6894 |
| F1 | 0.8162 |

Kesinligin dusuk olmasi tasarim geregidir: triyaj bilerek cagri lehine
egiktir. Fazla gelen kayitlar gorev kuyruguna girmez, adres zenginlestirme
havuzuna duser.

### Tekillestirme - hacim problemi
| Metrik | Deger |
|---|---|
| Cagri → gorev | 9.939 → 985 (**10,1x**) |
| **Kume safligi** | **0.9898** |
| Olay kapsamasi | 0.9352 |
| Konumsuz havuz | 3.598 |

Kume safligi kritik: iki farkli enkaz tek goreve indirgenirse ikinci binaya
kimse gitmez. Bunu engelleyen kural, metin benzerliginin adres celiskisinin
yerine gecmemesidir.

### Zehirleme testi - saldirgan altinda
Saldirgan modeli **gercekci**: sozlukteki gercek mahalle ve sokak adlariyla,
yeni acilmis hesaplardan, yuksek paylasim baskisiyla 200 sahte ihbar.

| Metrik | Deger |
|---|---|
| Enjekte edilen | 200 |
| Kuyruga giren | 200 |
| **Ilk 10'a sizan** | **0** |
| **Ilk 100'e sizan** | **0** |
| Medyan yuzdelik | 0.669 |
| **Kaybolan gercek gorev** | **0** |

Ikinci satir olmadan birincisi anlamsizdir: her seyi bastiran bir sistem de
"basarili" gorunurdu. Basari, sahteyi asagi iterken gercege dokunmamaktir.

### Tazelik ve hiz
| Metrik | Deger |
|---|---|
| Bayat kayit kapatma orani | 1.0000 |
| Verim (tek cekirdek, saf Python) | 1.121 mesaj/sn |

---

## Kurulum ve kullanim

Cekirdek **sifir bagimlilikla** calisir - stdlib disinda hicbir sey gerekmez.

```bash
python -m sesver.cli demo                      # canli akis simulasyonu
python -m sesver.cli bench --messages 20000    # tam degerlendirme
python -m sesver.cli poison --mode gercekci    # zehirleme testi
python -m sesver.cli sevk                      # yonlendirme matrisi
python -m pytest -q                            # 32 test
```

Model egitimi icin (TRUBA):

```bash
pip install -e ".[train]"
bash scripts/truba/kurulum.sh     # ortam kontrolu
sbatch scripts/truba/sft.slurm    # QLoRA egitimi + degerlendirme kapisi
```

---

## Mimari

```
                    NSosyal olay veriyolu
                            |
                       [ TRIYAJ ]
                            |
        +-------------------+-------------------+
        |                                       |
   A HATTI (cagri)                        B HATTI (iddia)
        |                                       |
   [ COZUMLE ]  adres cikarimi            [ ETKI SKORU ]
   [ YER BUL ]  UAVT sozlugu              [ DEVRE KESICI ]  <= 15 dk, sureli
   [ BIRLESTIR] tekillestirme             [ CAPRAZ KONTROL ] DSI/TEIAS/Borsa
   [ DOGRULA  ] ucgenleme + durus         [ YETKILI ]        15 dk sayac
   [ ONCELIK  ] siddet x zaman x guven    [ GERI YAYILIM ]   soylentinin yolu
   [ KAPAT    ] bayatlama                        |
        |                                       |
        +-------------------+-------------------+
                            |
                     [ YONLENDIRME ]
                            |
   AFAD · saha ekibi · valilik · teknik kurum · saglik
   gonullu · vatandas · kamu · kolluk
```

Ayrintili aciklama: [`docs/mimari.md`](docs/mimari.md) ·
Entegrasyon plani: [`docs/entegrasyon.md`](docs/entegrasyon.md)

---

## Gizlilik - pazarlik disi iki kural

Bu iki kural `tests/test_gizlilik.py` tarafindan sinanir; ihlal eden bir
degisiklik testi kirar.

**1. Kolluga dogrulanmamis bireysel ihbar gitmez.** Yalnizca dogrulanmis
olaylar ve toplulastirilmis soylenti durumu iletilir.

**2. Kamuya kisisel veri gitmez.** Halka acik harita mahalle duzeyinde
toplulastirilir; isim, telefon ve saglik durumu yalnizca gorevi ustlenen
ekibe, yalnizca gorev suresince acilir.

Ayrintili degerlendirme: [`docs/veri-model-etik.md`](docs/veri-model-etik.md)

---

## Durustluk notlari

Bir afet sisteminde abartilmis iddia, eksik ozellikten daha tehlikelidir.
Bu deponun **su anda yapmadigi** seyler:

- **Kurum entegrasyonlari simulasyondur.** DSI, TEIAS, BOTAS ve Borsa
  Istanbul baglantilari `claims/registry.py` icinde sabit cevap donen
  fonksiyonlardir. Arayuz gercek entegrasyona uyacak sekilde tasarlanmistir;
  gerceklenmesi protokol ve yetkilendirme gerektirir.
- **Egitilmis model heniz yayinlanmadi.** Olculen tum sonuclar KURAL HATTINDAN
  gelir. Model hatti (`models/train_sft.py`) yazilmistir ve TRUBA'da kosmaya
  hazirdir; egitim sonuclari eklendiginde bu bolum guncellenecektir.
- **Veri sentetiktir.** Gercek afet mesajlari kisisel veri tasir; bir depoda
  yayinlanamaz. Sonuclarin gercekligi elle etiketlenmis kucuk bir altin set
  uzerinde dogrulanacaktir.
- **Adres sozlugu ornektir.** 3 il, 6 ilce, 23 mahalle. Uretimde UAVT ve bina
  envanteri kullanilir.

---

## Lisans

Apache-2.0. Bkz. [`LICENSE`](LICENSE).

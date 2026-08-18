# Mimari

## Neden iki hat

| | A HATTI - yardim cagrisi | B HATTI - sistemik iddia |
|---|---|---|
| Hacim | Yuz binlerce | Onlarca |
| Tek kaydin etkisi | 1 bina, 1 ekip | Milyonlarca kisi, panik, tahliye |
| Yanlis negatif maliyeti | Bir aile olur | Uyari gec kalir |
| Yanlis pozitif maliyeti | Bos bina, kayip kapasite | Kitlesel panik, yol tikanir |
| Strateji | **Silme, sirala** | **Yavaslat, dogrula, geri yayinla** |
| Karar suresi | Dakikalar | Saniyeler |

Ekonomileri zit oldugu icin kod yollari da ayridir. Ortak olan tek sey
triyaj asamasi ve yonlendirme matrisidir.

## A hatti - asama asama

### 1. AYIKLA (`pipeline/triage.py`)
Her mesaji dort sinifa ayirir: cagri / iddia / destek / gurultu.

Tasarim: **yuksek anma icin ayarli.** Bir yardim cagrisini gurultu sanmak geri
donusu olmayan bir hatadir; gurultuyu cagri sanmak yalnizca kuyruga bir satir
ekler. `cagri_egimi` sabiti bu asimetrinin sayisal karsiligidir.

### 2. COZ (`pipeline/extract.py`)
Serbest metinden yapilandirilmis alanlar: il / ilce / mahalle / sokak / bina /
kat / kisi sayisi / kirilganlik / canlilik isareti.

En kirilgan nokta burasi. Ornek girdiler:

```
antakya armutlu mah 5. sok yilmaz apt 3. kat 4 kisiyiz sesler geliyor
ADIYAMAN SITELER MAH. BINA COKTU 2 COCUK ICERIDE
Defne'de anneannem var haber alamiyoruz lutfen
```

Yakalanan tuzak: *"siteler mah bina coktu"* ifadesinde bina adi "mah"
degildir. `_YAPI_SOZCUKLERI` kumesi adres yapisi sozcuklerinin ad olarak
alinmasini engeller.

### 3. YER BUL (`data/gazetteer.py`)
Mahalle adindan koordinata, yazim hatasina toleransli. Esik 0.82: dusurmek
yanlis konumlandirmaya, yukseltmek kaydi kaybetmeye yol acar. Yanlis
konumlandirma daha tehlikeli oldugu icin esik yuksek tutulur - eslesme
bulunamazsa kayit daha kaba cozunurlukte kalir, yanlis yere gitmez.

### 4. BIRLESTIR (`pipeline/dedup.py`)
Hacim problemi burada cozulur. Uc sinyal: mekan yakinligi (haversine), metin
benzerligi, zaman penceresi.

**Kritik kural: metin benzerligi adres celiskisinin yerine gecmez.**

Afet cagrilarinin cogu ayni kaliptan cikar. Iki farkli binanin metinleri %80
benzer olabilir. Yalnizca metne bakan bir kumeleyici komsu iki enkazi tek
goreve indirger ve ikinci binaya kimse gitmez. Bu yuzden `_uyumlu()` alanlari
tek tek karsilastirir: iki tarafta da dolu olan bir alan celisiyorsa adresler
farklidir, benzerlik ne olursa olsun.

`bagimsiz_kaynak` ile `kopya_sayisi` ayrimi onemlidir: ayni hesabin 50 tekrari
guveni artirmaz, iki farkli hesabin ayni binayi bildirmesi ucgenlemedir.

**Konumsuz cagrilar** gorev kuyruguna sokulmaz. Konumu olmayan bir kayit
sahaya gonderilemez; ayri havuzda toplanip gonullu panelinde adres
zenginlestirmesine duser. Kayit yine silinmez, dogru kuyruga gider.

### 5. DOGRULA (`pipeline/verify.py`)
Guven dort sinyalden toplanir:

| Sinyal | Kaynak | Katki araligi |
|---|---|---|
| Ucgenleme | bagimsiz kaynak sayisi | -0.08 … +0.33 |
| Durus | yanit zincirindeki teyit/yalanlama | -0.45 … +0.25 |
| Hesap | yas, bolge gecmisi | -0.20 … +0.10 |
| Adres | konum cozunurlugu | -0.25 … +0.18 |

Durus analizi soylenti dogrulama yazinindan (RumourEval/PHEME hatti) gelir:
kalabalik kendi kendini duzeltir. Altindaki cevaplarda *"kurtarildilar"*,
*"bu adres yok"*, *"bu 3 gun onceki"* yazar.

Siralama onemlidir: `cozuldu > yalanlama > sorgu > teyit`. *"dogru mu"* bir
sorudur, teyit degildir.

### 6. ONCELIKLENDIR (`pipeline/prioritize.py`)
```
oncelik = siddet × zaman_baskisi × √guven × eylem_carpani
```

Zaman baskisi "altin 72 saat" egrisini izler: hizli yukselis, yuksek plato.
Karekok, guveni siralama carpani yapar - eleme kapisi degil.

### 7. KAPAT (`pipeline/close.py`)
Uc kapanma yolu: sahibi kapatir (tek dokunus), kalabalik kapatir (durus),
ekip kapatir (kurum paneli). Hicbiri gelmezse gorev **silinmez, bayatlar**;
kuyrukta gorunur kalir, en alta iner, yeniden teyit istenir.

### 8. AKTAR (`pipeline/route.py`)
Yonlendirme matrisi. Her alici farkli bir gorunum alir. Bkz. `entegrasyon.md`.

## B hatti - asama asama

| Asama | Dosya | Sure hedefi |
|---|---|---|
| Tespit | `claims/detect.py` | < 5 sn |
| Etki skoru | `claims/impact.py` | < 2 sn |
| Devre kesici | `claims/breaker.py` | < 10 sn |
| Capraz kontrol | `claims/registry.py` | < 30 sn |
| Yetkili yonlendirme | `claims/registry.py` | 15 dk pencere |
| Geri yayilim | `claims/backprop.py` | < 60 sn |

### Tespit
Nesne ve fiil **birlikte** gecmelidir: *"baraj"* tek basina haberdir,
*"baraj patladi"* iddiadir. Aksi halde normal haberler de kesiciyi
tetiklerdi.

### Etki skoru
```
etki = 0.55 × tur_tabani + 0.30 × ivme + 0.20 × eylem_tetikleyici
```

Ucuncu terim en kritigidir. *"Baraj su seviyesi yuksek"* ile *"Baraj patladi,
herkes yuksek yere kacsin"* ayni bilgiyi tasir; ikincisi trafigi kilitler,
kurtarma araclarinin gecisini engeller, izdiham riski yaratir.

### Devre kesici - sansure donusmesini engelleyen dort kilit
1. **Silme yok** - icerik durur, yalnizca oneri akisindan cikar, paylasim oncesi surtunme gelir
2. **Sureli** - otomatik kesici en fazla 15 dk; uzatma insan onayi ister
3. **Seffaf** - her karar kamuya acik gunluge yazilir
4. **Yalnizca afet modunda** - normal zamanda mekanizma kapalidir

Kurum suresinde cevap vermezse kesici **duser**; durum kamuya "yanitsiz"
gorunur. Sessizlik, kalici kisitlamanin gerekcesi olamaz.

### Geri yayilim
Duzeltmenin klasik problemi yanlis kitleye ulasmasidir. Platform yayilim
grafigini elinde tuttugu icin duzeltmeyi **tam olarak soylentiyi gorenlere**
gonderir. Olculen sey erisim degil **kapsama**.

## Neden genel amacli bir ajan cercevesi degil

`pipeline/graph.py` tipli bir durum grafigidir. Uc gerekce:

1. **Belirlenimcilik** - ayni girdi ayni cikti. Kurtarma kararlari yeniden
   uretilebilir olmali. `test_uctan_uca_kosum_belirlenimci` bunu sinar.
2. **Denetlenebilirlik** - her asamanin suresi ve her kararin gerekcesi
   `Gorev.iz` icine yazilir.
3. **Ariza davranisi** - fail-open. Model cokerse hat susmaz; siralama ve
   kesici devre disi kalir, ham akis gecmeye devam eder. Bir afet sisteminin
   asla yapmamasi gereken sey susmaktir.

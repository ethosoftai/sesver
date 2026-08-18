# Veri, model, etik ve performans

Bu belge NSosyal Inovasyon Yarismasi sartnamesindeki *"Veri, model, etik ve
performans dokumani"* teslimat kalemine karsilik gelir.

## 1. Veri

### 1.1 Neden sentetik

Gercek afet mesajlari ozel nitelikli kisisel veri tasir: isim, telefon, tam
adres, saglik durumu, akrabalik iliskisi. Bir yarisma deposunda bunlari
yayinlamak KVKK acisindan da etik acidan da savunulamaz.

Bu yuzden:
- **Egitim ve kosum verisi sentetiktir** (`data/synth.py`)
- **Dogrulama**, elle etiketlenmis kucuk bir altin set uzerinde yapilir
- Altin set depoda **yayinlanmaz**; yalnizca metrikleri raporlanir

### 1.2 Sentetik uretecin degeri

Uretec **yer gercegini birlikte uretir**: her mesajin hangi olaya ait oldugu,
gercek mi sahte mi, cozulmus mu oldugu bilinir. Tekillestirme orani, kume
safligi, sahte bastirma ve bayat kapatma metrikleri ancak boyle olculebilir.

| Sinif | Oran | Not |
|---|---|---|
| Gercek yardim cagrisi + kopyalari | ~%8 olay uretimi | kopya sayisi ussel dagilim |
| Sistemik iddia | ~%4 | 5 kalip, biri dogru |
| Destek teklifi | ~%10 | |
| Gurultu | kalan | dua, haber paylasimi, yorum |
| Sahte kampanya | olaylarin %6'si | yeni hesap, bolge gecmisi yok |

### 1.3 Adres sozlugu

Depoda ornek sozluk: 3 il, 6 ilce, 23 mahalle, 3 baraj
(`data/gazetteer_ornek.json`). Koordinatlar yaklasiktir ve yalnizca kosum
icindir.

**Uretimde** UAVT (Ulusal Adres Veri Tabani) ve bina envanteri kullanilir.
`data/gazetteer.py` arayuzu degismeden kaynak degistirilebilir.

### 1.4 Gercek veri kullanilacaksa

Yarisma sonrasi gercek arsiv metniyle calisilirsa uyulacak kurallar:
- Yalnizca **kamuya acik** paylasimlar
- Isim, telefon, TC ve hesap kimligi **yukleme aninda** maskelenir
- Ham metin egitim disina cikarilmaz, yalnizca turetilmis ozellikler saklanir
- Saklama suresi tanimlidir, olay kapandiktan sonra anonimlestirme zorunludur

## 2. Model

### 2.1 Neden kendi modelimizi egitiyoruz

Iki gerekce, ikisi de bagimsiz olarak yeterli:

**a) Afette ilk olen sey ag baglantisidir.** Bulut API'sine erisilemez. Model
koordinasyon merkezindeki dizustunde, hatta sahadaki gonullunun telefonunda
calismak zorundadir. Bu, 1-3B boyut ve INT4 kuantizasyon demektir.

**b) Panikle yazilmis Turkce adres cikarimini kuresel modeller yapamaz.**
Mahalle adlari, yerel referanslar, yarim cumleler, Turkce klavyesiz yazim.

### 2.2 Model ailesi

| Model | Boyut | Gorev | Yontem |
|---|---|---|---|
| DIVAN-AYIKLA | ~150M encoder | Triyaj | fine-tune + damitma |
| DIVAN-COZ | 1-3B | Alan cikarimi, JSON cikti | QLoRA SFT |
| DIVAN-DURUS | ~150M encoder | Yanit zinciri durus sinifi | fine-tune |

### 2.3 Egitim recetesi

```
Asama 1 - SFT:      QLoRA r=32, alpha=64, lr=1e-4, bf16, 3 epoch, packing
Asama 2 - Damitma:  COZ ciktilari -> AYIKLA ve DURUS
Asama 3 - Kuantizasyon: INT4 -> cevrimdisi kosum
Asama 4 - KAPI:     SES VER-Bench regresyon testi
```

**Degerlendirme kapisi zorunludur.** Gerileme varsa adaptor yayina alinmaz.
`scripts/truba/sft.slurm` egitimin hemen ardindan kapiyi kosar.

### 2.4 Donanim

TRUBA cuda-ui (ARF-ACC), kolyoz-cuda kuyrugu, 1x H100, 16 cekirdek.
Veri yurt disina cikmaz.

### 2.5 Mevcut durum - dogru bilgi

**Bu depodaki tum olculen sonuclar KURAL HATTINDAN gelmektedir.** Egitilmis
model heniz yayinlanmamistir. Model hatti yazilmis ve kosmaya hazirdir;
`ModelTriyaj` sarmalayicisi model yoksa sessizce kural hattina duser.

Bu, yaniltici bir eksiklik degil bilincli bir mimari karardir: model
bulunamamasi bir hata degil, bir **calisma kipidir** (fail-open).

## 3. Etik

### 3.1 Pazarlik disi iki kural

**Kolluga dogrulanmamis bireysel ihbar gitmez.** Yalnizca dogrulanmis olaylar
ve toplulastirilmis soylenti durumu iletilir. Dogrulanmamis bir soylentiyi
birey duzeyinde kolluga iletmek yurttas haklari acisindan savunulamaz.

**Kamuya kisisel veri gitmez.** Halka acik harita mahalle duzeyinde
toplulastirilir; isim, telefon ve saglik durumu yalnizca gorevi ustlenen
ekibe, yalnizca gorev suresince acilir.

Her ikisi de `tests/test_gizlilik.py` tarafindan sinanir.

### 3.2 Devre kesici ve ifade ozgurlugu

Devre kesici bir sansur araci degildir ve olmamasi kodda zorunlu tutulur:
silme yok, sureli (15 dk), kamuya acik gunluk, yalnizca afet modunda aktif.
Kurum yanit vermezse kesici duser.

Yine de bu, sistemin en hassas bileseni olarak kalir. Uretim dagitimi oncesi
bagimsiz bir hukuki ve etik inceleme gereklidir.

### 3.3 Insan son sozu

Otomatik olan: tespit, cikarim, konumlandirma, tekillestirme, durus analizi,
siralama, capraz kontrol, geri yayilim, bayat kapatma.

Insan onayi zorunlu: kesicinin 15 dakikayi asmasi, hesap kisitlamasi, resmi
"asilsiz" damgasi.

Asla otomatik degil: icerik silme, hesap kapatma.

### 3.4 Onyargi denetimi - planlanan

Yanlis pozitif orani lehce, cografya ve sosyoekonomik gosterge alt
kumelerinde ayri ayri raporlanacaktir. Aralarindaki fark 3 puani gecerse model
yayina alinmaz. **Bu denetim heniz kosulmamistir**; altin set genisletildikten
sonra eklenecektir.

## 4. Performans

Sentetik akis, 20.000 mesaj, tek cekirdek, model olmadan.

| Metrik | Deger | Hedef |
|---|---|---|
| Triyaj anmasi | 1.0000 | >= 0.99 |
| Kacan gercek cagri | 0 | 0 |
| Triyaj kesinligi | 0.6894 | tasarim geregi dusuk |
| Tekillestirme | 10,1x | - |
| Kume safligi | 0.9898 | >= 0.95 |
| Olay kapsamasi | 0.9352 | - |
| Bayat kapatma | 1.0000 | - |
| Zehirleme: ilk 100'e sizan | 0 | 0 |
| Zehirleme: kaybolan gercek | 0 | 0 |
| Verim | 1.121 mesaj/sn | - |

### 4.1 Bilinen sinirlar

- Sonuclar **sentetik** veriden gelir; gercek dagilim daha zordur
- Verim tek cekirdek ve saf Python olcumudur; uretimde toplu isleme ve
  derlenmis model ile buyuk fark beklenir
- Kurum entegrasyonlari **simulasyondur**
- Onyargi denetimi heniz kosulmamistir
- Adres sozlugu 23 mahalle ile sinirlidir

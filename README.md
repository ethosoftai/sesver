# SES VER

**Afet anında sosyal medyanın gürültüsünü, dakikalar içinde doğrulanmış bir kurtarma görev listesine çeviren ajan sistemi.**

TEKNOFEST 2026 · NSosyal İnovasyon Yarışması · Sosyal Yapay Zekâ dikeyi

```bash
git clone https://github.com/ethosoftai/sesver
cd sesver
python -m sesver.cli demo              # bağımlılık gerekmez, hemen koşar
python -m sesver.models.egit_ayikla    # modeli CPU'da ~15 sn'de eğitir
```

Çekirdek boru hattı, değerlendirme koşumu **ve model eğitimi** harici
bağımlılık olmadan çalışır: numpy yok, scikit-learn yok, PyTorch yok.
Afette ilk kesilen şey ağ bağlantısı, ikincisi kurulum yapabilme imkânıdır.

---

## Problem

| Sorun | Sonuç |
|---|---|
| Milyonlarca mesaj içinde gerçek çağrı kayboluyor | Ekip nereye gideceğini bilmiyor |
| Adresler serbest metin: *"Armutlu, 5. sokak, marketin arkası"* | Kayıt haritaya düşmüyor |
| Bir ailenin çağrısı 50.000 kez paylaşılıyor | Aynı bina defalarca görev açıyor |
| **Kurtarılmış insanların çağrısı günlerce dolaşıyor** | **Ekipler boşaltılmış binalara gidiyor** |
| Sahte ihbar ve dezenformasyon | Kıt kurtarma kapasitesi boşa harcanıyor |

## Çözüm: iki hat

**A HATTI — yardım çağrısı.** Yüz binlerce kayıt, her biri tek bir binayı
ilgilendirir. `ayıkla → çöz → yer bul → birleştir → doğrula → önceliklendir
→ aktar → kapat`

**B HATTI — sistemik iddia.** Onlarca kayıt, her biri milyonlarca kişiyi
ilgilendirir. *"Baraj patladı"* yanlışsa kitlesel paniğe, doğruysa geç
kalınmış bir tahliyeye yol açar.

Ekonomileri zıt olduğu için kod yolları da ayrıdır.

---

## Üç tasarım kararı

**1. Kayıt silinmez, sıralanır.** Gerçek bir çağrıyı elemek bir aileyi
kaybettirir; sahte bir çağrıyı geçirmek kıt kapasiteyi harcar ve o kapasite
başka yerde bir hayata mal olur. İkisi de ölümcül olduğu için ikili
doğru/yanlış sınıflandırması yanlış tasarımdır.

> Sistem neyin doğru olduğunu iddia etmiyor. **Yanlış olma maliyetini yönetiyor.**

**2. Öncelik güvene eşit değildir.**
`öncelik = şiddet × zaman_baskısı × √güven × eylem_çarpanı`
Karekök, güveni bir *sıralama çarpanına* dönüştürür; bir *eleme kapısına*
değil. Tek kaynaklı ama "üç çocuk var, sesler geliyor" diyen çağrı, iki
kaynaklı ama işaretsiz çağrının üstünde kalır.

**3. Metin benzerliği adres çelişkisinin yerine geçmez.** Çağrıların çoğu
aynı kalıptan çıkar; iki farklı binanın metinleri %80 benzer olabilir.
Yalnızca metne bakan bir kümeleyici komşu iki enkazı tek göreve indirger ve
ikinci binaya kimse gitmez.

---

## Yapay zekâ hattı

### DİVAN-AYIKLA — eğitilmiş triyaj sınıflandırıcısı

Karakter n-gram karma özellikleri üzerinde **ortalamalı perceptron**, saf
Python. 22.740 örnek, 8 epoch, **CPU'da 15 saniye**, 4.122 sıfır olmayan
ağırlık, 149 KB'lık tek JSON dosyası.

Neden büyük dil modeli değil: triyaj akıştaki *her* mesaja uygulanır, karar
bütçesi milisaniyelerdir. Doğru kaskad ucuz sınıflandırıcıyı her mesaja,
pahalı modeli yalnızca gri bölgeye uygular.

### Dürüst değerlendirme: şablon-ayrık test

Tüm şablonlar hem eğitimde hem testte kullanılırsa model şablon parmak izini
ezberler ve **F1 = 1,0000** üretir — gerçek dünyada hiçbir şey öngörmeyen bir
sayı. Bu depoda ilk ölçüm tam olarak böyle çıktı ve atıldı.

Bunun yerine şablon havuzu ikiye bölünür: model `a` yarısıyla eğitilir,
**`b` yarısıyla (daha önce hiç görmediği ifade biçimleriyle)** test edilir.
Ayrıca tüm metinlere gerçekçi yazım bozulması uygulanır (Türkçe karakter
kaybı, harf düşmesi, komşu tuş, uzatma, mesajın yarıda kesilmesi).

| Metrik | Kural hattı | Model | Birleşik |
|---|---|---|---|
| Doğruluk | 0,6714 | **0,7675** | 0,6515 |
| Makro F1 | 0,6832 | **0,7146** | 0,6404 |
| F1 (çağrı) | 0,6847 | **0,7690** | 0,6745 |
| F1 (gürültü) | 0,6223 | **0,7750** | 0,6073 |
| F1 (iddia) | **0,5475** | 0,5008 | 0,5095 |
| **Kaçan gerçek çağrı** | **0** | **22** | **0** |

### Bulgu: model tek başına triyaj kararını almamalı

Model genel doğrulukta kural hattını 9,6 puan yeniyor ve gürültü ayrımında
açık ara üstün. **Ama 22 gerçek yardım çağrısı kaçırıyor; kural hattı sıfır
kaçırıyor.** Afet bağlamında bu iki hata eşit ağırlıkta değildir.

Bu yüzden `BirlesikTriyaj` asimetriktir: **ÇAĞRI için kural VEYA model**
(anma korunur), diğer sınıflar için model. Birleşik hat kaçan çağrıyı sıfıra
indirir — ama genel doğrulukta kural hattının altında kalır. Dolayısıyla
üretimdeki triyaj kararı **kural hattında kalmaktadır**; model, doğrulama
katmanına ikinci görüş sinyali olarak beslenir; orada bir hata ölümcül değildir.

Bu, ölçümden çıkan bir mühendislik sonucudur, bir pazarlama cümlesi değil.

### Konformal kalibrasyon — garantili hata bütçesi

Softmax çıktıları kalibre değildir; "%92 eminim" hiçbir şey garanti etmez.
Bölünmüş konformal tahmin, modelin iç skorlarına hiç güvenmez: ayrı bir
kalibrasyon kümesinde gerçek hata dağılımını ölçer ve dağılımdan bağımsız
bir garanti verir — `P(gerçek sınıf ∈ C(x)) ≥ 1 − α`.

Tekil olmayan her tahmin kümesi insana devredilir. Bu, "kayıt silinmez,
sıralanır" ilkesinin model düzeyindeki karşılığıdır.

| α | Kapsama | Çekimserlik | Otomatik kararda doğruluk |
|---|---|---|---|
| 0,01 | 0,9910 | 0,0090 | 1,0000 |
| 0,02 | 0,9828 | 0,0172 | 1,0000 |
| 0,05 | 0,9502 | 0,0498 | 1,0000 |

Garanti sağlanıyor ve eğri teoriyle birebir uyumlu.

### Bulgu: çekimserlik oranı bir dağılım kayması alarmıdır

Konformal garanti, kalibrasyon ve üretim dağılımlarının değişmediği
varsayımına dayanır. Şablon-ayrık testte bu varsayım **kasıtlı olarak**
ihlal edilir ve kapsama 0,95'ten **0,3337**'ye düşer.

Kritik olan şu: sistem bunu sessizce yapmaz. Çekimserlik %5'ten **%66,6**'ya
fırlar. Yani model, görmediği bir dağılımla karşılaştığında yanlış karar
vermek yerine devrediyor ve bu devretme oranı ölçülebilir bir alarm sinyali
üretiyor. Sahada bu, "akışın karakteri değişti, modeli yeniden eğit"
uyarısına karşılık gelir.

---

## Ölçülen sonuçlar — boru hattı

20.000 mesajlık sentetik akış. **Gürültü ablasyonu**, yazım bozulmasının
maliyetini doğrudan ölçer:

| Metrik | Temiz şablon | Gerçekçi bozulma | Kabul eşiği |
|---|---|---|---|
| Triyaj anması | 1,0000 | **1,0000** | ≥ 0,99 |
| **Kaçan gerçek çağrı** | **0** | **0** | 0 |
| Tekilleştirme | 10,5× | 6,4× | — |
| Küme saflığı | 0,9867 | 0,8383 | ≥ 0,80 |
| Olay kapsaması | 0,9411 | 0,9402 | ≥ 0,90 |
| Bayat kayıt kapatma | 1,0000 | 0,6850 | — |
| Verim (tek çekirdek) | ~1.700 msj/sn | ~1.250 msj/sn | — |

**Okunuşu:** güvenlik özelliği — sıfır kaçan çağrı — gürültü altında
bozulmadan duruyor. Bozulan şey adres çözümlemesine dayanan metrikler: küme
saflığı 0,99'dan 0,84'e, bayat kapatma 1,00'dan 0,69'a iniyor. Bu düşüş
eğitilmiş çıkarım modelinin (DİVAN-ÇÖZ) kapatması gereken açığı sayısal
olarak tanımlar.

### Zehirleme testi

Saldırgan modeli bilinçli olarak zor: uydurma adres yerine **sözlükteki
gerçek mahalle ve sokak adları**, yeni açılmış hesaplar, yüksek paylaşım
baskısı.

| | |
|---|---|
| Enjekte edilen sahte kayıt | 200 |
| Kuyruğa giren | 200 |
| **İlk 100'e sızan** | **0** |
| **Kaybolan gerçek görev** | **0** |

İkinci satır olmadan birincisi anlamsızdır: her şeyi bastıran bir sistem de
"başarılı" görünürdü.

---

## Kullanım

```bash
python -m sesver.cli demo                      # canlı akış simülasyonu
python -m sesver.cli bench --messages 20000    # tam değerlendirme
python -m sesver.cli bench --gurultu 0         # temiz rejim (ablasyon)
python -m sesver.cli poison --mode gercekci    # zehirleme testi
python -m sesver.cli sevk                      # yönlendirme matrisi
python -m sesver.cli sunucu                    # JSON API
python -m sesver.cli altin-set                 # bağımsız gerçek veri doğrulaması
python -m pytest -q                            # 46 test

python -m sesver.models.sft_veri               # DİVAN-ÇÖZ için SFT verisi
python -m sesver.models.egit_ayikla            # eğitim + konformal kalibrasyon
```

TRUBA üzerinde büyük model eğitimi:

```bash
pip install -e ".[train]"
python -m sesver.models.sft_veri  # DİVAN-ÇÖZ için SFT verisi üretir
bash scripts/truba/kurulum.sh     # ortam kontrolü
sbatch scripts/truba/sft.slurm    # QLoRA eğitimi + değerlendirme kapısı
```

SFT etiketleri kural tabanli `Cozumleyici`'nin ciktisi degil, sentetik
uretecin bildigi yer gercegidir - aksi halde model gecmesi beklenen taban
cizgisini taklit ederdi. Ayrinti: `src/sesver/models/sft_veri.py`.

---

## Gizlilik — pazarlık dışı iki kural

`tests/test_gizlilik.py` tarafından sınanır; ihlal eden değişiklik testi kırar.

1. **Kolluğa doğrulanmamış bireysel ihbar gitmez.**
2. **Kamuya kişisel veri gitmez.** Halka açık harita mahalle düzeyinde
   toplulaştırılır.

---

## Dürüstlük notları

Bir afet sisteminde abartılmış iddia, eksik özellikten daha tehlikelidir.

- **TRUBA'da büyük model eğitimi yapılmadı.** SLURM betikleri ve 15.117
  örneklik SFT veri kümesi hazır; küme erişimi bu çalışma sırasında
  sağlanamadı. Eğitilen ve raporlanan model, CPU'da koşan DİVAN-AYIKLA'dır.
- **Kurum entegrasyonları simülasyondur.** DSİ, TEİAŞ, BOTAŞ ve Borsa
  İstanbul bağlantıları sabit cevap dönen fonksiyonlardır; arayüz gerçek
  entegrasyona uyacak biçimde tasarlanmıştır.
- **Eğitim verisi sentetiktir.** Gerçek afet mesajları kişisel veri taşır ve
  bir depoda yayımlanamaz. Bağımsız doğrulama için 6 Şubat 2023 depremine ait
  elle etiketlenmiş gerçek bir altın set kullanılır (`sesver.eval.altin_set`);
  ham metin depoda tutulmaz, yalnızca tweet kimliği ve etiket.
- **Adres sözlüğü örnektir.** 3 il, 6 ilçe, 23 mahalle. Üretimde UAVT ve
  bina envanteri kullanılır.
- **Arayüz yoktur.** Bilinçli tercih: değeri üreten şey ekrandaki kutular
  değil, arkasındaki hattır. JSON API herhangi bir istemciye açıktır.

---

## Lisans

Apache-2.0. Bkz. [`LICENSE`](LICENSE).

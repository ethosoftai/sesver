# Kaynak: avaapm/deprem (Toraman ve ark., 2023)

`avaapm_deprem_id_etiket.tsv` bu depodan alinmistir:
https://github.com/avaapm/deprem

## Icerik

1000 tweet ID'si, ikili etiket (yardim cagrisi var/yok) ve varlik etiketleri
(PERSON/CITY/ADDRESS/STATUS, karakter ofseti olarak). **Ham tweet metni
icermez** - kaynak depo da metni dagitmiyor, ayni gerekceyle:
gizlilik ve Twitter/X kullanim sartlari.

Bu dosya PII icermez (yalnizca sayisal ID ve etiket), bu yuzden depoda
tutulabilir. Metin gerekiyorsa `sesver.eval.altin_set.hidrat()` ile X API
uzerinden coz "hidrate" edilir; hidrat edilmis sonuc `data/gold/` altina
yazilir ve **asla commit edilmez** (bkz. `.gitignore`), tipki
`docs/veri-model-etik.md` bolum 1.1'de tanimlanan altin set kuraliyla
tutarli sekilde.

## Lisans

Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
(CC BY-NC-SA 4.0). Tam metin: `LICENSE` dosyasinda.

**NC (NonCommercial) kaydina dikkat**: bu veri seti yalnizca akademik/
yarisma degerlendirmesi icin kullanilabilir, ticari urun degerlendirmesinde
kullanilamaz.

## Atif

```bibtex
@misc{toraman2023earthquake,
  doi = {10.48550/ARXIV.2302.13403},
  url = {https://arxiv.org/abs/2302.13403},
  author = {Toraman, Cagri and Kucukkaya, Izzet Emre and Ozcelik, Oguzhan and Sahin, Umitcan},
  title = {Tweets Under the Rubble: Detection of Messages Calling for Help in Earthquake Disaster},
  publisher = {arXiv},
  year = {2023},
  copyright = {Creative Commons Attribution Non Commercial Share Alike 4.0 International}
}
```

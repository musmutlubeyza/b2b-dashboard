# BookWise – Intelligence Platform

![BookWise](assets/logo_full.png)

B2B kitap dağıtımı için karar destek paneli.

İTÜ ISL 533 Veri Madenciliği dersi kapsamında, bir B2B kitap dağıtımcısının 2020 yılı satış verisiyle
hazırlanan Streamlit gösterge paneli. Panel; satış, pazarlama ve tedarik zinciri departmanları için
KPI'lar, analizler, tahminler ve kural tabanlı aksiyon önerileri sunar.

**Canlı panel:** https://bookwise-intelligence-platform.streamlit.app/

## Sayfalar

| Sayfa | İçerik |
|---|---|
| Yönetici Özeti | KPI'lar (önceki dönemle karşılaştırmalı), haftalık ciro ve 8 haftalık tahmin, segmentler, çeyrekler, en çok değişen kategoriler |
| Satış ve Müşteri | Müşteri hareketi, RFM segmentleri, kayıp riski (churn) modeli, il performansı |
| Pazarlama ve Segmentler | K-ortalamalar segment profilleri, kategori penetrasyonu, çapraz satış, iskonto analizi |
| Ürün ve Tedarik | ABC-XYZ stok sınıflandırması, haftalık iş yükü, en çok satan başlıklar |
| Tahmin | Haftalık ciro/adet tahmini, model karşılaştırması, kategori tahminleri |
| Veri Notları | Temizleme adımları, kategori standardizasyonu, varsayımlar, yöntemler, aksiyon ve filtre kuralları |

Filtreler (dönem, il, ana kategori, müşteri segmenti) tüm sayfalarda ortaktır ve sayfa geçişlerinde korunur.
Sağ alttaki "Panele sor" sohbeti sayfanın öne çıkan bulgularını ve hazır soruların yanıtlarını gösterir.

## Yöntemler

- **Veri ön işleme:** Tekrar eden ve geçersiz satırların temizlenmesi, Excel'in bozduğu ürün adlarının düzeltilmesi,
  il adlarının standardizasyonu, 305 kategori etiketinin 15 ana kategorili üç düzeyli hiyerarşiye eşlenmesi
  (denetim tablosu: `data/processed/category_mapping.csv`).
- **Segmentasyon:** K-ortalamalar (k = 4), log ölçekli ve standartlaştırılmış 6 davranış değişkeni.
- **RFM:** Son alım, sıklık ve tutar için 1–5 dilim puanları.
- **Kayıp riski:** Lojistik regresyon; zamansal testte yalnızca "son alımdan geçen gün" kuralıyla karşılaştırılır.
- **ABC-XYZ:** Ciro payı (%80 / %95) ve aylık talep değişkenlik katsayısı (0,5 / 1,0).
- **Tahmin:** Naive, doğrusal trend ve üstel düzeltme son 6 hafta üzerinde sınanır; aykırı haftalar Hampel
  filtresiyle sınırlanır; %80 tahmin aralığı verilir.
- **Aksiyon motoru:** Her öneri açık bir kurala ve veriden gelen bir kanıta dayanır (kurallar Veri Notları'nda).

## Proje yapısı

```
streamlit_app.py        Giriş noktası: tema, üst gezinme, ortak filtreler
app_pages/              Altı sayfanın kodu
src/                    Hesap ve arayüz modülleri
  data_prep.py          Ham Excel → temiz parquet (python -m src.data_prep)
  categories.py         Kategori hiyerarşisi ve eşleme sözlüğü
  segments.py, rfm.py, churn.py, forecast.py, metrics.py, actions.py
  filters.py, charts.py, ui.py, style.py, chat.py, config.py
data/                   Ham veri ve temizlenmiş veri (data/processed)
.streamlit/config.toml  Tema
```

## Yerelde çalıştırma

Python 3.12 gerekir.

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.data_prep        # yalnızca veri hazırlama kodu değiştiğinde
streamlit run streamlit_app.py
```

## Sınırlılıklar

Veri yalnızca 2020 yılını kapsar (pandemi yılı); stok, maliyet ve iade bilgisi yoktur. Ayrıntılar panelin
Veri Notları sayfasındadır.

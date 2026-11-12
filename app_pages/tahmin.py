"""Tahmin: haftalık satış tahmini, model karşılaştırması ve kategori tahminleri."""

import streamlit as st

from src import charts
from src.actions import category_signals, horizon_label, monitoring, targets_from_forecast
from src.config import FORECAST_TABS
from src.data_loader import load_category_forecasts, load_forecast
from src.forecast import FOLD_HORIZON, MIN_ACTIVE_WEEKS, TEST_WEEKS
from src.formatting import fmt_date, fmt_number, fmt_pct, fmt_tl, tr_lower
from src.ui import action_cards, html_table, kpi_card, page_tabs, section_header

f = st.session_state["filters"]
st.title("Tahmin")
st.caption("Model 2020'nin tüm haftalarıyla kurulur; il, kategori ve segment filtreleri tahmin edilen seriyi daraltır.")

c1, c2, c3 = st.columns([1.3, 1.2, 1.3])
series = c1.segmented_control("Seri", ["Ciro", "Adet"], default="Ciro", key="fc_series",
                              help="Ciro: yönetim ve pazarlama hedefleri için. Adet: tedarik planlaması "
                                   "(depo kapasitesi, sipariş miktarı) için.") or "Ciro"
horizon = int((c2.segmented_control("Ufuk", ["4 hafta", "8 hafta", "12 hafta"], default="8 hafta", key="fc_h")
               or "8 hafta").split()[0])
adjust = (c3.segmented_control("Veri", ["Düzeltilmiş", "Ham veri"], default="Düzeltilmiş", key="fc_adjust",
                               help="Düzeltilmiş: 20 ve 27 Temmuz haftaları (kayıt boşluğu) enterpolasyonla doldurulur; "
                                    "pandemi döneminde 5 haftalık ortancadan 3 MAD'den fazla sapan haftalar sınırlanır.")
          or "Düzeltilmiş") == "Düzeltilmiş"
value, unit = ("Revenue", "TL") if series == "Ciro" else ("Quantity", "adet")
fmt = fmt_tl if unit == "TL" else (lambda v: f"{fmt_number(v)} adet")

r = load_forecast(f.cities, f.categories, f.segments, value, horizon, adjust, subcategories=f.subcategories)
if not r["enough_data"]:
    st.warning(f"Seçili il, kategori ve segment için seride yalnızca {r['active_weeks']} haftada satış var. "
               f"Güvenilir tahmin için en az {MIN_ACTIVE_WEEKS} hafta gerekir; filtreleri genişletin.")
    st.stop()

t, test = r["table"], r["test"]
best, naive = r["best"], t.loc["Naive", "mape"]
k = st.columns(4)
with k[0]:
    kpi_card(0, f"Önümüzdeki {horizon} hafta", fmt(r["total"]), note=f"{horizon_label(r['forecast'])}; yöntem: {tr_lower(best)}")
with k[1]:
    kpi_card(1, "%80 tahmin aralığı", f"{fmt(r['total_lo'])} – {fmt(r['total_hi'])}".replace(" TL –", " –"),
             note="Gerçekleşmenin 10 olasılıktan 8'inde bu aralıkta kalması beklenir")
with k[2]:
    kpi_card(2, "Doğrulama hatası (MAPE)", fmt_pct(t.loc[best, "mape"]),
             note=f"{best}; {r['n_folds']} kayan doğrulama adımının ortalaması")
with k[3]:
    kpi_card(3, "Son test hatası (MAPE)", fmt_pct(test[best]),
             note=f"Seçimde kullanılmayan son {TEST_WEEKS} hafta; naive {fmt_pct(test['Naive'])}")

cats = load_category_forecasts(f.cities, f.categories, f.segments, value, horizon, adjust, subcategories=f.subcategories)
main, side = st.columns([3.4, 1], gap="large")
with main:
    t1, t2, t3, t4 = page_tabs(FORECAST_TABS, "tabs_fc")
    with t1:
        section_header(f"Haftalık {tr_lower(series)} ve tahmin", badge="Dönem filtresinden bağımsız")
        st.plotly_chart(charts.forecast_chart(r, unit), config=charts.CONFIG, theme=None)
        parts = ["İlk ve son hafta kısmi olduğu için modelde kullanılmadı; 28 Aralık haftası grafikte içi boş noktayla "
                 "gösterilir ve tahmin bu haftadan geçerek 4 Ocak'a bağlanır (toplamlara katılmaz)."]
        if adjust:
            parts.append("Kare işaretler kayıt boşluğu nedeniyle doldurulan, halkalar pandemi döneminde sınırlanan haftalardır.")
        st.caption(" ".join(parts))
    with t2:
        section_header("Model karşılaştırması")
        st.caption(f"Kayan başlangıçlı doğrulama: her model {fmt_date(r['cv_start'].date())} haftasından başlayarak "
                   f"{r['n_folds']} kez, o noktaya kadarki veriyle kuruldu ve sonraki {FOLD_HORIZON} haftayı tahmin etti. "
                   "Ön işleme her seferinde yalnızca eğitim penceresine uygulandı (veri sızıntısı yok). En düşük ortalama "
                   f"MAPE'li model seçildi; son {TEST_WEEKS} hafta seçimde hiç kullanılmadı ve yalnızca raporlandı.")
        about = {"Naive": "Son haftanın değerini tekrar eder (referans)",
                 "Doğrusal trend": "Yıl boyunca haftalık doğrusal eğilim (en küçük kareler)",
                 "Üstel düzeltme": "Holt yöntemi: seviye ve sönümlü trend; yakın geçmişe daha çok ağırlık"}
        html_table(["Model", "Doğrulama MAE", "Doğrulama MAPE", "Son test MAPE", "Ne yakalar"],
                   [[f"<b>{m}</b>" + (" ✓" if m == best else ""), fmt(row.mae),
                     f"<b>{fmt_pct(row.mape)}</b>" if m == best else fmt_pct(row.mape), fmt_pct(test[m]), about[m]]
                    for m, row in t.iterrows()],
                   ["left", "right", "right", "right", "left"])
        st.caption("%80 aralık: kayan doğrulama hatalarının karekök ortalaması (RMSE) × 1,28 × √(hafta sırası). "
                   + ("Seçilen model naive referansını geçtiği için tahmine dayalı öneriler gösteriliyor."
                      if r["beats_naive"] else
                      "Hiçbir model kayan doğrulamada naive referansını geçemedi; tahmin naive yöntemle verilir ve "
                      "tahmine dayalı öneriler gösterilmez. Yıl içindeki pandemi kırılması trend modellerini yanıltıyor."))
    with t3:
        section_header("Kategori tahminleri")
        st.caption("Kapsamdaki en büyük 5 kategori; her biri için ayrı model seçildi. Sinyal yalnızca model naive "
                   "referansını geçtiğinde ve tahmin aralığı son 8 haftanın ortalamasından tamamen ayrıldığında verilir.")
        rows = []
        for c in cats.itertuples():
            if not c.enough:
                rows.append([f"<b>{c.category}</b>", "—", "—", "—", "—", f"Yetersiz veri ({c.active_weeks} hafta)"])
            else:
                sig = {"artış": '<span class="up">▲ Artış</span>', "düşüş": '<span class="down">▼ Düşüş</span>'}.get(c.signal, "Belirgin değişim yok")
                rows.append([f"<b>{c.category}</b>", fmt(c.last8), fmt(c.mean), f"{fmt(c.lo)} – {fmt(c.hi)}",
                             f"{c.model} ({fmt_pct(c.mape)})", sig])
        html_table(["Kategori", "Son 8 hafta ort.", "Tahmin ort.", "%80 aralık (haftalık)", "Model (doğrulama MAPE)", "Sinyal"],
                   rows, ["left", "right", "right", "right", "left", "left"])
    with t4:
        section_header("Bu tahmini okurken")
        st.markdown(
            "1. Veri yalnızca 2020'yi kapsıyor; yıllık mevsimsellik (ör. okul sezonu, yılbaşı) tek yıldan öğrenilemez.\n"
            "2. 2020 pandemi nedeniyle olağan dışı bir yıl; tahmin kısıtlamaların tekrarlanmayacağını varsayar.\n"
            f"3. Model seçimi {r['n_folds']} kayan doğrulama adımına ({r['n_folds'] * FOLD_HORIZON} hafta) dayanıyor; "
            "örneklem küçük olduğu için modeller arasındaki farklar temkinle okunmalı.\n"
            "4. Ufuk uzadıkça aralık genişler; 8 haftadan uzun tahminler yön göstergesi olarak okunmalı.\n"
            f"5. Süzülmüş seride 51 tam haftanın {MIN_ACTIVE_WEEKS}'ından azında satış varsa tahmin yapılmaz.\n"
            "6. Ürün düzeyinde tahmin yapılmaz: ortanca ürün yılda yalnızca 4 gün satılıyor.")

with side:
    acts = [targets_from_forecast(r) if value == "Revenue" else None]
    acts += category_signals(cats, "Tedarik" if value == "Quantity" else "Pazarlama")
    acts.append(monitoring())
    action_cards([a for a in acts if a is not None])

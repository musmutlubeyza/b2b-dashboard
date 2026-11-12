"""Tahmin: haftalık satış tahmini, model karşılaştırması ve kategori tahminleri."""

import streamlit as st

from src import charts
from src.actions import category_signals, horizon_label, monitoring, targets_from_forecast
from src.chat import render_chat
from src.data_loader import load_category_forecasts, load_forecast
from src.filters import describe
from src.forecast import HOLDOUT, MIN_ACTIVE_WEEKS
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.ui import action_cards, html_table, kpi_card, section_header

f = st.session_state["filters"]
st.title("Tahmin")
st.caption("Model 2020'nin tüm haftalarıyla kurulur; il, kategori ve segment filtreleri tahmin edilen seriyi daraltır.")

c1, c2, c3 = st.columns([1, 1.2, 1.3])
series = c1.segmented_control("Seri", ["Ciro", "Adet"], default="Ciro", key="fc_series") or "Ciro"
horizon = int((c2.segmented_control("Ufuk", ["4 hafta", "8 hafta", "12 hafta"], default="8 hafta", key="fc_h") or "8 hafta").split()[0])
cap = (c3.segmented_control("Aykırı haftalar", ["Sınırla", "Ham veri"], default="Sınırla", key="fc_cap",
                            help="Sınırla: 5 haftalık hareketli ortancadan 3 MAD'den fazla sapan haftalar (ör. pandemi "
                                 "dip ve sıçramaları) modelde ortancayla değiştirilir.") or "Sınırla") == "Sınırla"
value, unit = ("Revenue", "TL") if series == "Ciro" else ("Quantity", "adet")
fmt = fmt_tl if unit == "TL" else (lambda v: f"{fmt_number(v)} adet")

r = load_forecast(f.cities, f.categories, f.segments, value, horizon, cap, subcategories=f.subcategories)
if not r["enough_data"]:
    st.warning(f"Seçili il, kategori ve segment için seride yalnızca {r['active_weeks']} haftada satış var. "
               f"Güvenilir tahmin için en az {MIN_ACTIVE_WEEKS} hafta gerekir; filtreleri genişletin.")
    st.stop()

t = r["table"]
best, naive = r["best"], t.loc["Naive", "mape"]
k = st.columns(4)
with k[0]:
    kpi_card(0, f"Önümüzdeki {horizon} hafta", fmt(r["total"]), note=horizon_label(r["forecast"]))
with k[1]:
    kpi_card(1, "%80 tahmin aralığı", f"{fmt(r['total_lo'])} – {fmt(r['total_hi'])}".replace(" TL –", " –"),
             note="Gerçekleşmenin 10 olasılıktan 8'inde bu aralıkta kalması beklenir")
with k[2]:
    kpi_card(2, "Doğrulama hatası (MAPE)", fmt_pct(t.loc[best, "mape"]), note=f"{best}; son {HOLDOUT} hafta saklanarak ölçüldü")
with k[3]:
    kpi_card(3, "Naive modele göre", f"{fmt_number((naive - t.loc[best, 'mape']) * 100, 1)} puan",
             note=f"Naive hatası {fmt_pct(naive)}; daha düşük hata daha iyi")

cats = load_category_forecasts(f.cities, f.categories, f.segments, value, horizon, cap, subcategories=f.subcategories)
main, side = st.columns([3.4, 1], gap="large")
with main:
    t1, t2, t3, t4 = st.tabs(["Haftalık tahmin", "Model karşılaştırması", "Kategori tahminleri", "Sınırlılıklar"])
    with t1:
        section_header(f"Haftalık {series.lower()} ve tahmin", badge="Dönem filtresinden bağımsız")
        st.plotly_chart(charts.forecast_chart(r, unit), config=charts.CONFIG, theme=None)
        n_flag = int(r["flagged"].sum())
        st.caption("İlk ve son hafta kısmi olduğu için seriden çıkarıldı. "
                   + (f"Aykırı {n_flag} hafta modelde sınırlandı (halkalı noktalar). " if cap and n_flag else "")
                   + "Gri bant modelin sınandığı son 6 haftayı gösterir.")
    with t2:
        section_header("Model karşılaştırması")
        st.caption(f"Her model son {HOLDOUT} hafta saklanarak sınandı; en düşük MAPE'li model seçildi.")
        about = {"Naive": "Son haftanın değerini tekrar eder (referans)",
                 "Doğrusal trend": "Yıl boyunca haftalık doğrusal eğilim",
                 "Üstel düzeltme": "Seviye ve sönümlü trend; yakın geçmişe daha çok ağırlık"}
        html_table(["Model", "MAE", "MAPE", "RMSE", "Ne yakalar"],
                   [[f"<b>{m}</b>" + (" ✓" if m == best else ""), fmt(row.mae), f"<b>{fmt_pct(row.mape)}</b>" if m == best else fmt_pct(row.mape),
                     fmt(row.rmse), about[m]] for m, row in t.iterrows()],
                   ["left", "right", "right", "right", "left"])
        st.caption("%80 aralık: seçilen modelin doğrulama hatası (RMSE) × 1,28 × √(hafta sırası). "
                   + ("Model naive referansını geçtiği için tahmine dayalı öneriler gösteriliyor."
                      if r["beats_naive"] else "Model naive referansını geçemediği için tahmine dayalı öneriler gösterilmiyor."))
    with t3:
        section_header("Kategori tahminleri")
        st.caption("Kapsamdaki en büyük 5 kategori; her biri için ayrı model seçildi. Sinyal yalnızca tahmin aralığı "
                   "son 8 haftanın ortalamasından tamamen ayrıldığında verilir.")
        rows = []
        for c in cats.itertuples():
            if not c.enough:
                rows.append([f"<b>{c.category}</b>", "—", "—", "—", "—", f"Yetersiz veri ({c.active_weeks} hafta)"])
            else:
                sig = {"artış": '<span class="up">▲ Artış</span>', "düşüş": '<span class="down">▼ Düşüş</span>'}.get(c.signal, "Belirgin değişim yok")
                rows.append([f"<b>{c.category}</b>", fmt(c.last8), fmt(c.mean), f"{fmt(c.lo)} – {fmt(c.hi)}",
                             f"{c.model} ({fmt_pct(c.mape)})", sig])
        html_table(["Kategori", "Son 8 hafta ort.", "Tahmin ort.", "%80 aralık (haftalık)", "Model (MAPE)", "Sinyal"],
                   rows, ["left", "right", "right", "right", "left", "left"])
    with t4:
        section_header("Bu tahmini okurken")
        st.markdown(
            "1. Veri yalnızca 2020'yi kapsıyor; yıllık mevsimsellik (ör. okul sezonu, yılbaşı) tek yıldan öğrenilemez.\n"
            "2. 2020 pandemi nedeniyle olağan dışı bir yıl; tahmin kısıtlamaların tekrarlanmayacağını varsayar.\n"
            "3. Doğrulama yalnızca 6 haftaya dayanıyor; model farkları bu küçük örneklemde değişebilir.\n"
            "4. Ufuk uzadıkça aralık genişler; 8 haftadan uzun tahminler yön göstergesi olarak okunmalı.\n"
            f"5. Süzülmüş seride 52 haftanın {MIN_ACTIVE_WEEKS}'ından azında satış varsa tahmin yapılmaz.\n"
            "6. Ürün düzeyinde tahmin yapılmaz: ortanca ürün yılda yalnızca 4 gün satılıyor.")

with side:
    acts = [targets_from_forecast(r) if value == "Revenue" else None]
    if value == "Revenue":
        acts += category_signals(cats, "Tedarik")
    acts.append(monitoring())
    action_cards([a for a in acts if a is not None])

highlights = [f"{horizon_label(r['forecast'])} için tahmin {fmt(r['total'])} (%80 aralığı {fmt(r['total_lo'])} – {fmt(r['total_hi'])}).",
              f"Seçilen model {best}; doğrulama hatası {fmt_pct(t.loc[best, 'mape'])}, naive {fmt_pct(naive)}.",
              f"Son 8 haftanın haftalık ortalaması {fmt(r['last8_mean'])}; toplam seride belirgin sinyal: {r['signal']}."]
fc = r["forecast"]
answers = {"İlk 4 hafta için beklenti ne?": f"{horizon_label(fc.iloc[:4])}: {fmt(fc['point'].iloc[:4].sum())}.",
           "Hangi kategoride değişim bekleniyor?": ("; ".join(f"{c.category}: {c.signal}" for c in cats.itertuples() if c.enough)
                                                   or "Yeterli verisi olan kategori yok.")}
answers["Model ne kadar güvenilir?"] = (
    f"Seçilen model {best}; son 6 haftalık doğrulamada hata (MAPE) {fmt_pct(t.loc[best, 'mape'])}, naive referansınki "
    f"{fmt_pct(naive)}. Tek yıllık veri nedeniyle 8 haftadan uzun ufuklar yön göstergesi olarak okunmalı.")
render_chat("forecast", describe(f), highlights, answers)

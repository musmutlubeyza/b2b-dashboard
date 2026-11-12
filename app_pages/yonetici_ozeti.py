"""Yönetici Özeti: seçili dönemin büyük resmi, önceki dönemle karşılaştırmalı."""

import streamlit as st

from src import charts
from src.actions import horizon_label, plan_with_forecast, summary_actions
from src.chat import render_chat
from src.config import PAGE_FORECAST, PAGE_MARKETING, PAGE_SALES, PAGE_SUPPLY, PERIODS
from src.data_loader import load_data, load_forecast
from src.filters import apply_filters, comparison_label, describe, period_name, previous_period
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.metrics import category_movers, kpis, lost_customers, quarter_revenue, segment_shares, weekly_revenue
from src.ui import action_cards, kpi_card, panel_link, section_header

df, _ = load_data()
f = st.session_state["filters"]
cur = apply_filters(df, f)
prev_f = previous_period(f, df["InvoiceDate"].min().date())
prev = apply_filters(df, prev_f) if prev_f else None

st.title("Yönetici Özeti")
st.caption(f"Karşılaştırma: {period_name(prev_f)}." if prev_f else "Karşılaştırma yok: seçili dönemden önce veri bulunmuyor.")

if cur.empty:
    st.info("Seçili filtrelerle eşleşen işlem yok. Filtreleri genişletin.")
    st.stop()

# --- KPI kartları ---
k = kpis(cur)
pk = kpis(prev) if prev is not None and not prev.empty else None
comp = comparison_label(f)
change = lambda key: (k[key] / pk[key] - 1) if pk and pk[key] else None
cards = [("Net ciro", fmt_tl(k["revenue"]), "revenue", fmt_tl, PAGE_SALES),
         ("Fatura sayısı", fmt_number(k["invoices"]), "invoices", fmt_number, PAGE_SUPPLY),
         ("Ortalama fatura tutarı", fmt_tl(k["avg_invoice"]), "avg_invoice", fmt_tl, PAGE_MARKETING),
         ("Alım yapan müşteri", fmt_number(k["customers"]), "customers", fmt_number, PAGE_SALES)]
for i, (col, (label, value, key, fmt, page)) in enumerate(zip(st.columns(4), cards)):
    with col:
        kpi_card(i, label, value, change(key), comp, fmt(pk[key]) if pk else "", page)

main, side = st.columns([3.4, 1], gap="medium")
with main:
    left, right = st.columns([3, 2], gap="small")
    with left, st.container(key="panel_trend"):
        section_header("Haftalık net ciro")
        trend = weekly_revenue(cur, f.start, f.end)
        prev_trend = weekly_revenue(prev, prev_f.start, prev_f.end) if prev is not None else None
        # Tahmin yalnızca dönem yıl sonunu içeriyorsa ve model naive referansını geçiyorsa gösterilir
        fc_r = load_forecast(f.cities, f.categories, f.segments, subcategories=f.subcategories) if f.end >= df["InvoiceDate"].max().date() else None
        show_fc = bool(fc_r and fc_r["enough_data"] and fc_r["beats_naive"])
        st.plotly_chart(charts.period_trend(trend, prev_trend, period_name(f), period_name(prev_f) if prev_f else None,
                                            forecast=fc_r["forecast"] if show_fc else None),
                        config=charts.CONFIG, theme=None)
        if show_fc:
            st.caption(f"Önümüzdeki 8 hafta ({horizon_label(fc_r['forecast'])}): **{fmt_tl(fc_r['total'])}**, "
                       f"%80 aralığı {fmt_tl(fc_r['total_lo'])} – {fmt_tl(fc_r['total_hi'])}.")
        elif fc_r is None:
            st.caption("Tahmin yalnızca seçili dönem yıl sonunu içerdiğinde gösterilir.")
        else:
            st.caption("Seçili filtrelerde güvenilir tahmin üretilemedi; ayrıntı Tahmin sayfasında.")
        panel_link(PAGE_FORECAST, "Tüm yıl ve model")
    with right, st.container(key="panel_segments"):
        section_header("Müşteri segmentleri", badge="Segment filtresi: vurgular")
        seg = segment_shares(apply_filters(df, f, ignore=("segment",)))
        st.plotly_chart(charts.segment_bars(seg, f.segments), config=charts.CONFIG, theme=None)
        panel_link(PAGE_MARKETING, "Segment ayrıntıları")

    left, right = st.columns(2, gap="small")
    with left, st.container(key="panel_quarters"):
        section_header("Çeyreklere göre net ciro", badge="Dönem filtresi: vurgular")
        q = quarter_revenue(apply_filters(df, f, ignore=("period",)))
        selected = [i for i in q.index if PERIODS[f"{i}. Çeyrek 2020"][0] <= f.end and PERIODS[f"{i}. Çeyrek 2020"][1] >= f.start]
        st.plotly_chart(charts.quarter_bars(q, selected), config=charts.CONFIG, theme=None)
    with right, st.container(key="panel_movers"):
        section_header("En çok değişen kategoriler")
        if prev is None or prev.empty:
            st.info("Önceki dönem olmadığı için karşılaştırma yapılamıyor.")
        elif 0 < len(f.subcategories) < 3:
            st.info("Bu karşılaştırma için en az 3 alt kategori seçili olmalı ya da alt kategori filtresi boş bırakılmalı.")
        else:
            movers = category_movers(cur, prev)
            st.plotly_chart(charts.movers_bars(movers), config=charts.CONFIG, theme=None)
        panel_link(PAGE_SUPPLY, "Ürün ayrıntıları")

with side:
    actions = summary_actions(cur, prev, f, prev_f) if prev is not None else []
    if show_fc:
        actions.append(plan_with_forecast(fc_r))
    action_cards(actions, note=None if prev is not None else "Karşılaştırmalı öneriler için önceki dönem gerekir.")

# --- Sohbet (hazır sorular; model bağlantısı sonraki bölümde) ---
highlights, answers = [], {}
if pk:
    move = lambda key: f"{fmt_pct(abs(change(key)))} {'arttı' if change(key) >= 0 else 'azaldı'}"
    highlights.append(f"Ciro {comp} {move('revenue')}; fatura sayısı {move('invoices')}, "
                      f"ortalama fatura tutarı {move('avg_invoice')}.")
    lost = lost_customers(cur, prev)
    if not lost.empty:
        highlights.append(f"Önceki dönemde ({period_name(prev_f)}) alım yapan {fmt_number(len(lost))} müşteri bu dönemde alım yapmadı "
                          f"(önceki dönem cirosu {fmt_tl(lost['revenue'].sum())}).")
        answers["Kaybedilme riski olan müşteriler"] = "En büyük kaybedilen müşteriler: " + "; ".join(
            f"{cid} ({r.city}, {fmt_tl(r.revenue)})" for cid, r in lost.head(3).iterrows()) + "."
    m = category_movers(cur, prev, n=1)
    if not m.empty and m["diff"].iloc[0] > 0:
        top = m.index[0]
        highlights.append(f"En çok büyüyen kategori {top} (+{fmt_tl(m['diff'].iloc[0])}).")
        answers["En çok büyüyen kategori"] = f"{top}: önceki döneme göre +{fmt_tl(m['diff'].iloc[0])}."
else:
    highlights.append(f"Seçili dönemde net ciro {fmt_tl(k['revenue'])}, alım yapan müşteri {fmt_number(k['customers'])}.")
if pk:
    answers["Cironun değişimini ne açıklıyor?"] = (
        f"Ciro {comp} {fmt_pct(abs(change('revenue')))} {'arttı' if change('revenue') >= 0 else 'azaldı'}. "
        f"Alım yapan müşteri {fmt_pct(abs(change('customers')))}, fatura sayısı {fmt_pct(abs(change('invoices')))}, "
        f"ortalama fatura tutarı {fmt_pct(abs(change('avg_invoice')))} "
        f"{'arttı' if change('avg_invoice') >= 0 else 'azaldı'}; değişimin ağırlığı fatura sayısında mı tutarda mı, buradan okunur.")
if show_fc:
    answers["Önümüzdeki 8 haftada ne bekleniyor?"] = (
        f"{horizon_label(fc_r['forecast'])} için tahmini ciro {fmt_tl(fc_r['total'])}; %80 aralığı "
        f"{fmt_tl(fc_r['total_lo'])} – {fmt_tl(fc_r['total_hi'])}. Ayrıntı Tahmin sayfasında.")
wd = cur.groupby("Weekday")["Quantity"].sum()
answers["Pazartesi iş yükü"] = f"Seçili dönemde satılan adetin {fmt_pct(wd.get(0, 0) / wd.sum())} kadarı pazartesi günü."
render_chat("summary", describe(f), highlights, answers)

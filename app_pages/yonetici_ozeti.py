"""Yönetici Özeti: seçili dönemin büyük resmi, önceki dönemle karşılaştırmalı."""

import pandas as pd
import streamlit as st

from src import charts
from src.actions import plan_with_forecast, summary_actions
from src.chat import render_assistant
from src.config import PAGE_FORECAST, PAGE_MARKETING, PAGE_SALES, PAGE_SUPPLY, PERIODS
from src.data_loader import load_data, load_forecast
from src.filters import apply_filters, comparison_label, period_name, previous_period
from src.formatting import fmt_number, fmt_tl, tr_lower
from src.metrics import category_movers, kpis, quarter_revenue, segment_shares, weekly_revenue
from src.ui import action_cards, kpi_card, panel_link, section_header, segment_period_note

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
cards = [("Net ciro", fmt_tl(k["revenue"]), "revenue", fmt_tl, PAGE_SALES, "İl Performansı"),
         ("Fatura sayısı", fmt_number(k["invoices"]), "invoices", fmt_number, PAGE_SUPPLY, "İş Yükü"),
         ("Ortalama fatura tutarı", fmt_tl(k["avg_invoice"]), "avg_invoice", fmt_tl, PAGE_MARKETING, "Segment Profilleri"),
         ("Alım yapan müşteri", fmt_number(k["customers"]), "customers", fmt_number, PAGE_SALES, "Müşteri Hareketi")]
for i, (col, (label, value, key, fmt, page, tab)) in enumerate(zip(st.columns(4), cards)):
    with col:
        kpi_card(i, label, value, change(key), comp, fmt(pk[key]) if pk else "", page, tab=tab)

main, side = st.columns([3.4, 1], gap="medium")
with main:
    left, right = st.columns([3, 2], gap="small")
    with left, st.container(key="panel_trend"):
        section_header("Haftalık net ciro")
        trend = weekly_revenue(cur, f.start, f.end)
        prev_trend = weekly_revenue(prev, prev_f.start, prev_f.end) if prev is not None else None
        # Kısmi haftalar: dönem ya da veri sınırında 7 günden az kalan haftalar
        lo = max(pd.Timestamp(f.start), df["InvoiceDate"].min())
        hi = min(pd.Timestamp(f.end), df["InvoiceDate"].max())
        days = pd.Series([(min(w + pd.Timedelta(days=6), hi) - max(w, lo)).days + 1 for w in trend.index], index=trend.index)
        # Tahmin yalnızca dönem yıl sonunu içerdiğinde gösterilir
        fc_r = (load_forecast(f.cities, f.categories, f.segments, subcategories=f.subcategories)
                if f.end >= df["InvoiceDate"].max().date() else None)
        show_fc = bool(fc_r and fc_r["enough_data"])
        st.plotly_chart(charts.period_trend(trend, prev_trend, period_name(f), period_name(prev_f) if prev_f else None,
                                            days=days, forecast=fc_r["forecast"] if show_fc else None,
                                            bridge=fc_r["bridge"] if show_fc else None),
                        config=charts.CONFIG, theme=None)
        if show_fc:
            st.caption(f"8 haftalık tahmin: **{fmt_tl(fc_r['total'])}**, %80 aralığı {fmt_tl(fc_r['total_lo'])} – "
                       f"{fmt_tl(fc_r['total_hi'])} ({tr_lower(fc_r['best'])}).")
        elif fc_r is None:
            st.caption("Tahmin yalnızca seçili dönem yıl sonunu içerdiğinde gösterilir. İçi boş noktalar kısmi haftalardır.")
        else:
            st.caption("Seçili filtrelerde güvenilir tahmin üretilemedi; ayrıntı Tahmin sayfasında.")
        panel_link(PAGE_FORECAST, "Tüm yıl ve model", "Haftalık Tahmin")
    with right, st.container(key="panel_segments"):
        section_header("Müşteri segmentleri", badge=["Yıl sonu", "Filtre: vurgular"])
        seg = segment_shares(apply_filters(df, f, ignore=("segment",)))
        st.plotly_chart(charts.segment_bars(seg, f.segments), config=charts.CONFIG, theme=None)
        segment_period_note(f, df["InvoiceDate"].max().date())
        panel_link(PAGE_MARKETING, "Segment ayrıntıları", "Segment Profilleri")

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
        panel_link(PAGE_SUPPLY, "Ürün ayrıntıları", "En Çok Satan Başlıklar")

with side:
    actions = summary_actions(cur, prev, f, prev_f) if prev is not None else []
    if show_fc and fc_r["beats_naive"]:  # tahmine dayalı öneri yalnızca model naive referansını geçerse
        actions.append(plan_with_forecast(fc_r))
    action_cards(actions, note=None if prev is not None else "Karşılaştırmalı öneriler için önceki dönem gerekir.")

render_assistant(f)

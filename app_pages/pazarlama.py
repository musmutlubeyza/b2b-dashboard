"""Pazarlama ve Segmentler: segment profilleri, kategori penetrasyonu, çapraz satış ve iskonto."""

import pandas as pd
import streamlit as st

from src import charts
from src.actions import category_signals, cross_sell_campaign, discount_review
from src.config import MARKETING_TABS, PRIMARY, SEGMENT_SHORT, SEGMENTS, rgba
from src.data_loader import load_category_forecasts, load_data
from src.filters import apply_filters, comparison_label, period_name, previous_period
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.metrics import cross_sell, customer_discounts, penetration, segment_profiles
from src.ui import action_cards, html_table, kpi_card, page_tabs, section_header, segment_period_note

df, silhouette = load_data()
f = st.session_state["filters"]
cur = apply_filters(df, f)
prev_f = previous_period(f, df["InvoiceDate"].min().date())
prev = apply_filters(df, prev_f) if prev_f else None
all_seg = apply_filters(df, f, ignore=("segment",))                    # segment karşılaştırmaları
no_cat = apply_filters(df, f, ignore=("segment", "category"))          # penetrasyon ve çapraz satış

st.title("Pazarlama ve Segmentler")
st.caption(f"Karşılaştırma: {period_name(prev_f)}." if prev_f else "Karşılaştırma yok: seçili dönemden önce veri bulunmuyor.")
if cur.empty:
    st.info("Seçili filtrelerle eşleşen işlem yok. Filtreleri genişletin.")
    st.stop()

profiles = segment_profiles(all_seg, f.end)
rate, missing = penetration(no_cat)
targets = cross_sell(rate, missing)
disc = customer_discounts(cur)["discount"]
w_disc = 1 - cur["Revenue"].sum() / cur["ListValue"].sum()

# --- KPI kartları ---
c = st.columns(4)
with c[0]:
    core = SEGMENTS[0]
    kpi_card(0, "Çekirdek Kitabevleri'nin ciro payı", fmt_pct(profiles.loc["share", core]),
             note=f"{fmt_number(profiles.loc['customers', core])} müşteri; segment filtresinden bağımsız")
with c[1]:
    if prev is not None and not prev.empty:
        p_disc = 1 - prev["Revenue"].sum() / prev["ListValue"].sum()
        pts = (w_disc - p_disc) * 100
        # Daha düşük iskonto kâr marjı için olumlu: azalış yeşil
        note = (f'<span class="{"up" if pts <= 0 else "down"}">{"▼" if pts <= 0 else "▲"} {fmt_number(abs(pts), 1)} puan</span>'
                f' {comparison_label(f)} ({fmt_pct(p_disc)})')
    else:
        note = "Karşılaştırma için önceki dönem verisi yok"
    kpi_card(1, "Ağırlıklı ortalama iskonto", fmt_pct(w_disc), note=note)
with c[2]:
    kpi_card(2, "Müşteri ortanca iskontosu", fmt_pct(disc.median()), note="Müşteri bazında ağırlıklı oranların ortancası")
with c[3]:
    if targets.empty:
        kpi_card(3, "Çapraz satış hedefi", "—", note="Kurala uyan kategori yok")
    else:
        t = targets.iloc[0]
        kpi_card(3, "Çapraz satış hedefi", f"{fmt_number(t['missing'])} müşteri", note=f"{t['segment']}, {t['category']}")

main, side = st.columns([3.4, 1], gap="large")
with main:
    t_prof, t_cross, t_disc = page_tabs(MARKETING_TABS, "tabs_mkt")

    with t_prof:
        section_header("Segment profilleri", badge=["2020 yıl sonu segmentleri", "Segment filtresi: vurgular"])
        st.caption(f"Segmentler 2020 yıl sonu davranışından k-ortalamalarla belirlendi (4 küme, silhouette "
                   f"{fmt_number(silhouette, 2)}); ölçüler seçili döneme göre hesaplanır.")
        segment_period_note(f, df["InvoiceDate"].max().date())
        p = profiles
        share = lambda v: "%0,1’den az" if 0 < v < 0.001 else fmt_pct(v)
        rows = [("Bu dönemde alım yapan", lambda s: fmt_number(p.loc["customers", s])),
                ("Ciro payı", lambda s: share(p.loc["share", s])),
                ("Ortanca fatura sayısı", lambda s: fmt_number(p.loc["invoices", s])),
                ("Ortanca son alım", lambda s: f"{fmt_number(p.loc['recency', s])} gün önce"),
                ("Ortanca kategori çeşidi", lambda s: fmt_number(p.loc["categories", s])),
                ("Ortanca fatura tutarı", lambda s: fmt_tl(p.loc["basket", s])),
                ("Çocuk kitabı payı", lambda s: fmt_pct(p.loc["kids", s])),
                ("Ortanca iskonto", lambda s: fmt_pct(p.loc["discount", s]))]
        hl = lambda s: f"<b>{s}</b>" if (not f.segments or s in f.segments) else f'<span class="muted">{s}</span>'
        html_table([""] + [hl(s) for s in SEGMENTS],
                   [[f"<b>{name}</b>"] + [("—" if pd.isna(p.loc['customers', s]) or not p.loc['customers', s] else fn(s)) for s in SEGMENTS]
                    for name, fn in rows], ["left"] + ["right"] * 4)

    with t_cross:
        a, b = st.columns([1.3, 1], gap="large")
        with a:
            section_header("Kategori penetrasyonu", badge="Kategori filtresinden bağımsız")
            st.caption("Segmentteki müşterilerin yüzde kaçı bu kategoriden bu dönemde alım yaptı.")
            cells = lambda v: (f'<span class="heat" style="background: {rgba(PRIMARY, 0.05 + 0.4 * v)}">{fmt_pct(v, 0)}</span>'
                               if pd.notna(v) else "—")
            short = lambda s: hl(s).replace(s, SEGMENT_SHORT[s])  # dar tabloda kısa segment adları
            html_table(["Kategori"] + [short(s) for s in SEGMENTS],
                       [[cat] + [cells(rate.loc[s, cat]) for s in SEGMENTS] for cat in rate.columns],
                       ["left"] + ["center"] * 4)
        with b:
            section_header("Çapraz satış fırsatları", badge="Kategori filtresinden bağımsız")
            st.caption("Alım oranı Çekirdek Kitabevleri segmentindekinin yarısından az olan kategoriler.")
            if targets.empty:
                st.info("Seçili filtrelerde kurala uyan çapraz satış fırsatı yok.")
            else:
                html_table(["Segment", "Kategori", "Almayan", "Segmentte", "Çekirdekte"],
                           [[r.segment, r.category, f"<b>{fmt_number(r.missing)}</b>", fmt_pct(r.rate, 0), fmt_pct(r.core_rate, 0)]
                            for r in targets.itertuples()], ["left", "left", "right", "right", "right"])
                seg_of = no_cat.groupby("CustomerID", observed=True)["Segment"].first()
                bought = set(no_cat.loc[no_cat["Category_Standardized"] == targets.iloc[0]["category"], "CustomerID"].unique())
                lst = seg_of[(seg_of == targets.iloc[0]["segment"]) & ~seg_of.index.isin(bought)].index
                st.download_button("Hedef listesini indir (CSV)",
                                   pd.Series(lst, name="CustomerID").to_csv(index=False).encode("utf-8-sig"),
                                   "capraz_satis_hedef.csv", "text/csv", type="primary")

    with t_disc:
        a, b = st.columns(2, gap="large")
        with a:
            section_header("Müşteri büyüklüğüne göre iskonto")
            cd = customer_discounts(cur)
            if len(cd) >= 5:
                cd["group"] = pd.qcut(cd["revenue"].rank(method="first"), 5, labels=False)
                g = cd.groupby("group")[["revenue", "list_value"]].sum()
                q = (1 - g["revenue"] / g["list_value"]).tolist()
                st.caption("Müşteriler bu dönemdeki cirolarına göre beş eşit gruba ayrıldı.")
                st.plotly_chart(charts.simple_bars(["En küçük %20", "2. grup", "3. grup", "4. grup", "En büyük %20"], q,
                                                   [fmt_pct(v) for v in q], [4]), config=charts.CONFIG, theme=None)
                st.caption(f"En büyük ve en küçük grup arasındaki fark {fmt_number(abs(q[4] - q[0]) * 100, 1)} puan.")
            else:
                st.info("Bu karşılaştırma için en az 5 müşteri gerekir.")
        with b:
            section_header("Müşterilerin iskonto dağılımı")
            bins = pd.cut(disc, [-1, 0.30, 0.35, 0.38, 0.40, 0.42, 0.45, 1.01]).value_counts().sort_index().tolist()
            st.plotly_chart(charts.simple_bars(["≤%30", "%30–35", "%35–38", "%38–40", "%40–42", "%42–45", ">%45"], bins,
                                               [fmt_number(v) for v in bins], [bins.index(max(bins))]),
                            config=charts.CONFIG, theme=None)
            st.caption(f"%35–45 aralığının dışında {fmt_number(bins[0] + bins[1] + bins[6])} müşteri var.")

with side:
    signals = category_signals(load_category_forecasts(f.cities, f.categories, f.segments, subcategories=f.subcategories), "Pazarlama")
    action_cards([a for a in [cross_sell_campaign(targets), *signals[:1], discount_review(disc)] if a is not None],
                 note=None if signals else "Tahmine dayalı kampanya sinyali yok: kategori tahminleri naive referansını "
                                           "geçemedi ya da son 8 haftadan belirgin ayrışmıyor.")

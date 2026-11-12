"""Satış ve Müşteri: müşteri hareketi, RFM, kayıp riski (churn) ve il performansı."""

import pandas as pd
import streamlit as st

from src import charts
from src.actions import key_account, risk_assignment, second_order
from src.data_loader import load_churn, load_data
from src.config import SALES_TABS
from src.filters import apply_filters, comparison_label, period_name, previous_period
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.metrics import city_table, customer_flow, inactive_customers, kpis
from src.rfm import ACTIONS, rfm_summary, rfm_table
from src.ui import action_cards, bar_cell, html_table, kpi_card, page_tabs, section_header

df, _ = load_data()
scores, model_report = load_churn()
f = st.session_state["filters"]
cur = apply_filters(df, f)
prev_f = previous_period(f, df["InvoiceDate"].min().date())
prev = apply_filters(df, prev_f) if prev_f else None
scope = apply_filters(df, f, ignore=("period",))  # müşterinin önceki alımlarını görmek için

st.title("Satış ve Müşteri")
st.caption(f"Karşılaştırma: {period_name(prev_f)}." if prev_f else "Karşılaştırma yok: seçili dönemden önce veri bulunmuyor.")
if cur.empty:
    st.info("Seçili filtrelerle eşleşen işlem yok. Filtreleri genişletin.")
    st.stop()

# Kayıp riski yalnızca il ve segment filtresine uyar (müşteri özellikleri)
customers = df.drop_duplicates("CustomerID").set_index("CustomerID")[["City", "Segment"]]
keep = pd.Series(True, index=customers.index)
if f.cities:
    keep &= customers["City"].isin(f.cities)
if f.segments:
    keep &= customers["Segment"].isin(f.segments)
risk = scores[scores.index.isin(customers.index[keep])]

# --- KPI kartları ---
k, pk = kpis(cur), (kpis(prev) if prev is not None and not prev.empty else None)
comp = comparison_label(f)
rpc, prpc = k["revenue"] / k["customers"], (pk["revenue"] / pk["customers"] if pk else None)
inactive = inactive_customers(cur, prev) if pk else None
c = st.columns(4)
with c[0]:
    kpi_card(0, "Alım yapan müşteri", fmt_number(k["customers"]),
             k["customers"] / pk["customers"] - 1 if pk else None, comp, fmt_number(pk["customers"]) if pk else "")
with c[1]:
    kpi_card(1, "Müşteri başına ciro", fmt_tl(rpc), rpc / prpc - 1 if prpc else None, comp, fmt_tl(prpc) if prpc else "")
with c[2]:
    kpi_card(2, "Hareketsiz müşteri", fmt_number(len(inactive)) if inactive is not None else "—",
             note=(f"Önceki dönemde aldı, bu dönemde almadı; önceki dönem cirosu {fmt_tl(inactive['revenue'].sum())}"
                   if inactive is not None else "Önceki dönem verisi yok"))
with c[3]:
    kpi_card(3, "Riskteki ciro", fmt_tl(risk["risk_revenue"].sum()),
             note="Ocak–Mart 2021 tahmini; dönemden bağımsız")

main, side = st.columns([3.4, 1], gap="large")
flow = customer_flow(scope, cur, prev, f.start) if pk else None
with main:
    t_flow, t_rfm, t_risk, t_city = page_tabs(SALES_TABS, "tabs_sales")

    with t_flow:
        if flow is None:
            st.info("Müşteri hareketi önceki dönemle karşılaştırılarak hesaplanır; seçili dönem için önceki dönem verisi yok.")
        else:
            a, b = st.columns([3, 2], gap="large")
            with a:
                section_header(f"{period_name(prev_f)} → {period_name(f)}")
                st.plotly_chart(charts.customer_waterfall(flow, "Önceki dönem", "Seçili dönem"),
                                config=charts.CONFIG, theme=None)
            with b:
                section_header("Nasıl okunur")
                st.markdown(
                    f"- **Devam eden:** {fmt_number(flow['stay'])} müşteri iki dönemde de alım yaptı.\n"
                    f"- **Hareketsiz:** {fmt_number(flow['inactive'])} müşteri önceki dönemde alıp bu dönemde almadı. "
                    "Bu bir kayıp değil, gözlenen bir durum: bir kısmı sonraki dönemde geri dönebilir.\n"
                    f"- **Geri dönen:** {fmt_number(flow['back'])} müşteri önceki dönemde almadı; daha önce ve bu dönemde aldı.\n"
                    f"- **Yeni:** {fmt_number(flow['new'])} müşterinin veri içindeki ilk alımı bu dönemde.")

    with t_rfm:
        section_header("RFM segmentleri", badge="Kategori filtresinden bağımsız")
        hist = apply_filters(df, f, ignore=("period", "category"))
        hist = hist[hist["InvoiceDate"] <= pd.Timestamp(f.end)]
        summary = rfm_summary(rfm_table(hist, pd.Timestamp(f.end)))
        st.caption("Son alım (R), sıklık (F) ve tutar (M) 1–5 arası puanlandı; segmentler R puanı ile F ve M'nin "
                   "ortalaması (FM) üzerinden belirlendi. Dönem sonuna kadarki tüm geçmiş kullanılır.")
        top = summary["share"].max()
        html_table(["Segment", "Müşteri", "Ciro payı", "Ortanca son alım", "Ortanca fatura", "Öncelikli aksiyon"],
                   [[f"<b>{s}</b>", fmt_number(r.customers), bar_cell(r.share, top, fmt_pct(r.share)),
                     f"{fmt_number(r.recency)} gün", fmt_number(r.frequency), ACTIONS[s]] for s, r in summary.iterrows()],
                   ["left", "right", "left", "right", "right", "left"])

    with t_risk:
        a, b = st.columns([3, 2], gap="large")
        with a:
            section_header("Kayıp riski en yüksek ciro", badge="Dönem ve kategori filtresinden bağımsız")
            st.caption("Ocak–Mart 2021 için tahmin; riskteki ciroya (kayıp olasılığı × 2020 cirosu) göre sıralı.")
            top_risk = risk.head(8)
            html_table(["Müşteri", "İl", "Son alım", "Kayıp olasılığı", "2020 cirosu", "Riskteki ciro"],
                       [[f"<b>{cid}</b>", r.city, f"{r.last_purchase:%d.%m.%Y}", bar_cell(r.probability, 1, fmt_pct(r.probability, 0)),
                         fmt_tl(r.revenue), f"<b>{fmt_tl(r.risk_revenue)}</b>"] for cid, r in top_risk.iterrows()],
                       ["left", "left", "left", "left", "right", "right"])
            csv = risk.reset_index().rename(columns={"index": "CustomerID"}).to_csv(index=False, sep=";", decimal=",")
            st.download_button("Tüm listeyi indir (CSV)", csv.encode("utf-8-sig"), "kayip_riski.csv", "text/csv", type="primary")
        with b:
            section_header("Model nasıl çalışıyor")
            st.markdown("Kayıp: sonraki 92 günde hiç alım yapmamak. Lojistik regresyon; son alım, sıklık, ciro, "
                        "sipariş aralığı, iskonto ve kategori çeşidi.")
            m = model_report
            html_table(["", "Model", "Son alım kuralı"],
                       [["AUC (zamansal test)", f"<b>{fmt_number(m['auc_model'], 3)}</b>", fmt_number(m["auc_rule"], 3)],
                        ["En riskli %20'de isabet", f"<b>{fmt_pct(m['hit_model'])}</b>", fmt_pct(m["hit_rule"])]],
                       ["left", "right", "right"])
            st.caption("Model basit kuralı az farkla geçiyor; asıl katkısı kaybı müşterinin cirosuyla tartıp "
                       f"önceliklendirmesi. En riskli 20 müşterinin riskteki cirosu {fmt_tl(risk.head(20)['risk_revenue'].sum())}.")

    with t_city:
        section_header("İl performansı")
        ct = city_table(cur, prev)
        st.caption("Ciroya göre ilk 8 il" + ("; değişim önceki döneme göre." if "change" in ct else "."))
        arrow = lambda v: "—" if pd.isna(v) else f'<span class="{"up" if v >= 0 else "down"}">{"▲" if v >= 0 else "▼"} {fmt_pct(abs(v))}</span>'
        html_table(["İl", "Müşteri", "Ciro", "Değişim", "Müşteri başına ciro", "Ciro payı"],
                   [[f"<b>{city}</b>", fmt_number(r.customers), fmt_tl(r.revenue), arrow(r.get("change", float("nan"))),
                     fmt_tl(r.per_customer), fmt_pct(r.share)] for city, r in ct.iterrows()],
                   ["left", "right", "right", "right", "right", "right"])

with side:
    found = [risk_assignment(risk)]
    if pk:
        found += [key_account(cur, prev, f, prev_f), second_order(flow["new"])]
    action_cards([a for a in found if a is not None])

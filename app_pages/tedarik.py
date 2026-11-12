"""Ürün ve Tedarik: ABC-XYZ stok sınıflandırması, haftalık iş yükü ve en çok satan başlıklar."""

import streamlit as st

from src import charts
from src.actions import capacity, category_signals, safety_stock
from src.chat import render_chat
from src.config import PRIMARY, WEEKDAYS_TR, WEEKDAYS_TR_SHORT, rgba
from src.data_loader import load_category_forecasts, load_data
from src.filters import apply_filters, comparison_label, describe, period_name, previous_period
from src.formatting import fmt_number, fmt_pct
from src.metrics import abc_xyz, top_titles, weekday_share
from src.ui import action_cards, html_table, kpi_card, section_header

POLICY = {"AX": "Sürekli stok, yüksek servis düzeyi", "AY": "Emniyet stoku, sık gözden geçirme",
          "AZ": "Talebe yakın tedarik, yüksek emniyet stoku", "BX": "Otomatik yenileme", "BY": "Periyodik yenileme",
          "BZ": "Talebe göre tedarik", "CX": "Düşük stok, otomatik yenileme", "CY": "Minimum stok",
          "CZ": "Stoksuz, siparişe özel tedarik"}


@st.cache_data(show_spinner="ABC-XYZ hesaplanıyor...")
def abc_for(categories: tuple, subcategories: tuple = ()):
    """ABC-XYZ 2020'nin tamamıyla ve yalnızca kategori filtresiyle hesaplanır (stok kararı toplam talebe dayanır)."""
    df, _ = load_data()
    if categories:
        df = df[df["Main_Category"].isin(categories)]
    if subcategories:
        df = df[df["Category_Standardized"].isin(subcategories)]
    return abc_xyz(df)


df, _ = load_data()
f = st.session_state["filters"]
cur = apply_filters(df, f)
prev_f = previous_period(f, df["InvoiceDate"].min().date())
prev = apply_filters(df, prev_f) if prev_f else None

st.title("Ürün ve Tedarik")
st.caption(f"Karşılaştırma: {period_name(prev_f)}." if prev_f else "Karşılaştırma yok: seçili dönemden önce veri bulunmuyor.")
if cur.empty:
    st.info("Seçili filtrelerle eşleşen işlem yok. Filtreleri genişletin.")
    st.stop()

sku = abc_for(f.categories, f.subcategories)
shares = weekday_share(cur)
has_prev = prev is not None and not prev.empty
comp = comparison_label(f)

c = st.columns(4)
n_sku, n_qty = cur["StockCode"].nunique(), int(cur["Quantity"].sum())
with c[0]:
    p = prev["StockCode"].nunique() if has_prev else None
    kpi_card(0, "Satılan SKU", fmt_number(n_sku), n_sku / p - 1 if p else None, comp, fmt_number(p) if p else "")
with c[1]:
    p = int(prev["Quantity"].sum()) if has_prev else None
    kpi_card(1, "Satılan adet", fmt_number(n_qty), n_qty / p - 1 if p else None, comp, fmt_number(p) if p else "")
with c[2]:
    n_a = int((sku["abc"] == "A").sum())
    kpi_card(2, "A sınıfı SKU", fmt_number(n_a), note=f"2020 tamamı; cironun %80'i ({fmt_pct(n_a / len(sku))} SKU)")
with c[3]:
    kpi_card(3, "Pazartesi adet payı", fmt_pct(shares[0]),
             note=f"Salı–cuma ortalaması {fmt_pct(shares.iloc[1:5].mean())}")

main, side = st.columns([3.4, 1], gap="large")
with main:
    t_abc, t_load, t_top = st.tabs(["ABC-XYZ sınıflandırması", "İş yükü", "En çok satan başlıklar"])

    with t_abc:
        section_header("ABC-XYZ stok sınıflandırması", badge="Yalnızca kategori filtresine bağlı")
        st.caption("2020'nin tamamıyla hesaplanır. ABC ciroya katkıyı (%80 / %95), XYZ aylık talebin "
                   "öngörülebilirliğini (değişkenlik katsayısı 0,5 / 1,0) gösterir.")
        cells = sku.groupby(["abc", "xyz"]).agg(n=("revenue", "size"), revenue=("revenue", "sum"))
        total = sku["revenue"].sum()
        html = ['<div class="abc"><div></div>']
        for x, (t, s) in {"X": ("X: istikrarlı", "değişkenlik < 0,5"), "Y": ("Y: dalgalı", "0,5 – 1,0"),
                          "Z": ("Z: düzensiz", "1,0 ve üzeri")}.items():
            html.append(f'<div><div class="ch">{t}</div><div class="sub">{s}</div></div>')
        for a, sub in {"A": "Cironun ilk %80'i", "B": "Sonraki %15", "C": "Son %5"}.items():
            html.append(f'<div><div class="rh">{a}</div><div class="sub">{sub}</div></div>')
            for x in "XYZ":
                n, rev = (cells.loc[(a, x), "n"], cells.loc[(a, x), "revenue"]) if (a, x) in cells.index else (0, 0)
                alpha = 0.05 + 0.35 * min(1, rev / total / 0.45)
                html.append(f'<div class="cell" style="background: {rgba(PRIMARY, alpha)}"><div class="n">{fmt_number(n)} SKU</div>'
                            f'<div class="s">Ciro payı {fmt_pct(rev / total)}</div><div class="p">{POLICY[a + x]}</div></div>')
        st.markdown("".join(html) + "</div>", unsafe_allow_html=True)

    with t_load:
        a, b = st.columns([3, 2], gap="large")
        with a:
            section_header("Haftanın günlerine göre iş yükü")
            st.caption("Satılan adetin günlere dağılımı.")
            st.plotly_chart(charts.simple_bars(WEEKDAYS_TR_SHORT, shares.tolist(),
                                               [fmt_pct(v) for v in shares], [int(shares.idxmax())], height=260),
                            config=charts.CONFIG, theme=None)
        with b:
            section_header("Ne anlama geliyor")
            day = int(shares.idxmax())
            st.markdown(f"- En yoğun gün **{WEEKDAYS_TR[day].lower()}**: satılan adetin {fmt_pct(shares[day])} kadarı.\n"
                        f"- Salı–cuma ortalaması {fmt_pct(shares.iloc[1:5].mean())}.\n"
                        f"- Hafta sonu payı {fmt_pct(shares.iloc[5:].sum())}.")

    with t_top:
        section_header("En çok satan başlıklar")
        st.caption("Bu dönemde satılan adede göre; aynı kitabın farklı baskıları tek başlıkta toplandı.")
        tt = top_titles(cur)
        short = lambda s: s if len(s) <= 48 else s[:47].rstrip() + "…"
        html_table(["Başlık", "Kategori", "Adet", "Alan müşteri"],
                   [[f'<span title="{t}">{short(t)}</span>', r.category, fmt_number(r.quantity), fmt_number(r.customers)]
                    for t, r in tt.iterrows()], ["left", "left", "right", "right"])

with side:
    signals = category_signals(load_category_forecasts(f.cities, f.categories, f.segments, subcategories=f.subcategories), "Tedarik")
    action_cards([a for a in [*signals[:1], safety_stock(sku), capacity(shares)] if a is not None],
                 note=None if signals else "Tahmine dayalı sipariş sinyali yok: kategori tahminleri son 8 haftadan belirgin ayrışmıyor.")

az = sku[(sku["abc"] == "A") & (sku["xyz"] == "Z")]
highlights = [f"Bu dönemde {fmt_number(n_sku)} farklı SKU'dan {fmt_number(n_qty)} adet satıldı.",
              f"En yoğun gün {WEEKDAYS_TR[int(shares.idxmax())].lower()} (adetin {fmt_pct(shares.max())} kadarı)."]
answers = {"Hangi ürünlerde stok riski var?": (
    f"Stok verisi panelde olmadığı için stok seviyesini göremiyorum. Talep tarafında risk en yüksek grup AZ hücresi: "
    f"{fmt_number(len(az))} ürün, cironun {fmt_pct(az['revenue'].sum() / sku['revenue'].sum())} kadarı, aylık talebi düzensiz."),
    "En çok satan başlık": f"{top_titles(cur, 1).index[0]} ({fmt_number(top_titles(cur, 1)['quantity'].iloc[0])} adet)."}
answers["En yoğun gün hangisi?"] = (f"{WEEKDAYS_TR[int(shares.idxmax())]}: satılan adetin {fmt_pct(shares.max())} kadarı; "
                                   f"salı–cuma ortalaması {fmt_pct(shares.iloc[1:5].mean())}.")
answers["Kaç ürün A sınıfında?"] = (f"{fmt_number(n_a)} ürün (tüm ürünlerin {fmt_pct(n_a / len(sku))} kadarı) "
                                   "cironun %80'ini getiriyor.")
render_chat("supply", describe(f), highlights, answers)

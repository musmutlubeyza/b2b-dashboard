"""Ürün ve Tedarik: ABC-XYZ talep ve ciro önceliklendirmesi, adet tahmini, haftalık iş yükü ve en çok satan başlıklar."""

import pandas as pd
import streamlit as st

from src import charts
from src.actions import capacity, category_signals, close_monitoring, horizon_label, volume_plan
from src.config import PAGE_SUPPLY, PRIMARY, SUPPLY_TABS, WEEKDAYS_TR, WEEKDAYS_TR_SHORT, rgba
from src.data_loader import load_category_forecasts, load_data, load_forecast
from src.filters import apply_filters, comparison_label, period_name, previous_period
from src.formatting import fmt_number, fmt_pct, tr_lower
from src.metrics import abc_xyz, top_titles, weekday_share
from src.ui import action_cards, html_table, kpi_card, page_tabs, section_header

# Stok politikası değil, planlama önceliği: stok, tedarik süresi ve maliyet verisi olmadığı için
# matris stok miktarı hesaplamaz; hangi ürünlere öncelik ve dikkat ayrılacağını gösterir.
PRIORITY = {"AX": "Yüksek öncelik; talep öngörülebilir, düzenli planlamaya uygun",
            "AY": "Yüksek öncelik; sık gözden geçirme gerekir",
            "AZ": "Yüksek öncelik; yakın takip, tahminlere temkinli yaklaşım",
            "BX": "Orta öncelik; rutin planlama", "BY": "Orta öncelik; dönemsel gözden geçirme",
            "BZ": "Orta öncelik; talep geldikçe değerlendirme", "CX": "Düşük öncelik; basit kurallarla yönetilebilir",
            "CY": "Düşük öncelik", "CZ": "Düşük öncelik; siparişe özel tedarik adayı"}


@st.cache_data(show_spinner="ABC-XYZ hesaplanıyor...")
def abc_for(categories: tuple, subcategories: tuple = ()):
    """ABC-XYZ 2020'nin tamamıyla ve yalnızca kategori filtresiyle hesaplanır (öncelik toplam talebe dayanır)."""
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

# Adet tahmini: tedarik planlaması adetle yapılır (ciro fiyat karışımından etkilenir)
units = load_forecast(f.cities, f.categories, f.segments, "Quantity", 8, True, f.subcategories)

c = st.columns(4)
n_qty = int(cur["Quantity"].sum())
with c[0]:
    if units["enough_data"]:
        kpi_card(0, "Önümüzdeki 8 hafta (adet)", fmt_number(units["total"]),
                 note=f"{horizon_label(units['forecast'])}; yöntem: {tr_lower(units['best'])}", page=PAGE_SUPPLY,
                 tab="Adet Tahmini")
    else:
        kpi_card(0, "Önümüzdeki 8 hafta (adet)", "—", note="Seçili filtrelerde yeterli veri yok")
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
    t_abc, t_units, t_load, t_top = page_tabs(SUPPLY_TABS, "tabs_supply")

    with t_abc:
        section_header("ABC-XYZ talep ve ciro önceliklendirmesi", badge="Yalnızca kategori filtresine bağlı")
        st.caption("ABC ürünün ciroya katkısını (%80 / %95), XYZ aylık talebin ne kadar öngörülebilir olduğunu "
                   "(değişkenlik katsayısı 0,5 / 1,0) gösterir. Stok seviyesi, tedarik süresi ve maliyet verisi olmadığı "
                   "için bu matris stok miktarı hesaplamaz; planlamada hangi ürünlere öncelik ve dikkat ayrılacağını "
                   "gösterir. 2020'nin tamamıyla hesaplanır.")
        cells = sku.groupby(["abc", "xyz"]).agg(n=("revenue", "size"), revenue=("revenue", "sum"))
        total = sku["revenue"].sum()
        html = ['<div class="abc"><div></div>']
        for x, (t, s) in {"X": ("X: İstikrarlı", "değişkenlik < 0,5"), "Y": ("Y: Dalgalı", "0,5 – 1,0"),
                          "Z": ("Z: Düzensiz", "1,0 ve üzeri")}.items():
            html.append(f'<div><div class="ch">{t}</div><div class="sub">{s}</div></div>')
        for a, sub in {"A": "Cironun ilk %80'i", "B": "Sonraki %15", "C": "Son %5"}.items():
            html.append(f'<div><div class="rh">{a}</div><div class="sub">{sub}</div></div>')
            for x in "XYZ":
                n, rev = (cells.loc[(a, x), "n"], cells.loc[(a, x), "revenue"]) if (a, x) in cells.index else (0, 0)
                alpha = 0.05 + 0.35 * min(1, rev / total / 0.45)
                html.append(f'<div class="cell" style="background: {rgba(PRIMARY, alpha)}"><div class="n">{fmt_number(n)} SKU</div>'
                            f'<div class="s">Ciro payı {fmt_pct(rev / total)}</div><div class="p">{PRIORITY[a + x]}</div></div>')
        st.markdown("".join(html) + "</div>", unsafe_allow_html=True)

    with t_units:
        if not units["enough_data"]:
            st.info(f"Seçili filtrelerde seride yalnızca {units['active_weeks']} haftada satış var; adet tahmini için "
                    "en az 40 hafta gerekir.")
        else:
            a, b = st.columns([3, 1.3], gap="large")
            with a:
                section_header("Haftalık satılan adet ve tahmin", badge="Dönem filtresinden bağımsız")
                st.plotly_chart(charts.forecast_chart(units, "adet"), config=charts.CONFIG, theme=None)
                ut = units["table"]
                st.caption(f"Yöntem: {tr_lower(units['best'])}; kayan doğrulama hatası (MAPE) "
                           f"{fmt_pct(ut.loc[units['best'], 'mape'])}, son test {fmt_pct(units['test'][units['best']])}. "
                           + ("Kapasite planı önerisi bu modelin tahminine dayanır." if units["beats_naive"] else
                              "Hiçbir model naive referansını geçemediği için tahmin naive yöntemle (son haftaların "
                              "seviyesi) verilir. Kapasite planı bu referans tahminle yapılır; kategori sinyali gibi "
                              "model başarısına dayanan öneriler üretilmez."))
            with b:
                section_header("Beklenen günlük adet")
                recent = apply_filters(df, f, ignore=("period",))
                recent = recent[recent["InvoiceDate"] >= recent["InvoiceDate"].max() - pd.Timedelta(weeks=13)]
                ws = weekday_share(recent)
                weekly = units["forecast"]["point"].mean()
                st.caption(f"{horizon_label(units['forecast'])}; haftada ortalama {fmt_number(weekly)} adet, son 13 "
                           "haftanın gün dağılımına göre.")
                html_table(["Gün", "Pay", "Beklenen adet"],
                           [[WEEKDAYS_TR[d], fmt_pct(ws.get(d, 0)), f"<b>{fmt_number(weekly * ws.get(d, 0))}</b>"]
                            for d in range(7) if ws.get(d, 0) >= 0.005], ["left", "right", "right"])

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
            st.markdown(f"- En yoğun gün **{tr_lower(WEEKDAYS_TR[day])}**: satılan adetin {fmt_pct(shares[day])} kadarı.\n"
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
    # Sipariş kararı adetle verildiği için tedarik sinyalleri adet serisinden üretilir
    signals = category_signals(load_category_forecasts(f.cities, f.categories, f.segments, "Quantity",
                                                       subcategories=f.subcategories), "Tedarik")
    recent13 = apply_filters(df, f, ignore=("period",))
    recent13 = recent13[recent13["InvoiceDate"] >= recent13["InvoiceDate"].max() - pd.Timedelta(weeks=13)]
    plan = volume_plan(units, weekday_share(recent13))
    action_cards([a for a in [plan, *signals[:1], close_monitoring(sku), capacity(shares)] if a is not None], limit=4,
                 note=None if signals else "Tahmine dayalı sipariş sinyali yok: adet tahminleri naive referansını "
                                           "geçemedi ya da son 8 haftadan belirgin ayrışmıyor.")

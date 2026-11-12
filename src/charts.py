"""Plotly grafikleri; hepsi aynı stili (apply_style) kullanır.
Plotly İngilizce ay adı gösterdiği için eksen ve hover etiketleri Türkçe üretilir."""

import pandas as pd
import plotly.graph_objects as go

from src.config import (ACCENT, COMPARE, FONT_BODY, LINE, MONTHS_TR_SHORT, MUTED, PANDEMIC_BAND, PRIMARY,
                        PRIMARY_DARK, PRIMARY_LIGHT, SECONDARY, TEXT, rgba)
from src.formatting import fmt_pct, fmt_tl

CONFIG = {"displayModeBar": False}


def apply_style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=12, t=30, b=8), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
                      font=dict(family=FONT_BODY, size=12, color=TEXT),
                      hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(family=FONT_BODY, color=TEXT)))
    # fixedrange: panelde yakınlaştırma kapalı (araç çubuğu gizli olduğu için geri almak zordu)
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE, ticks="", tickfont=dict(color=MUTED), automargin=True,
                     fixedrange=True)
    fig.update_yaxes(gridcolor=LINE, zeroline=False, tickfont=dict(color=MUTED), automargin=True, fixedrange=True)
    return fig


def _tl_ticks(vmax: float) -> tuple[list[float], list[str]]:
    """Y ekseni için 3-4 adet okunur değer: '250 bin', '1 Mn'."""
    step = next(s for s in [50e3, 100e3, 250e3, 500e3, 1e6, 2e6, 5e6] if vmax / s <= 4)
    vals = [i * step for i in range(int(vmax // step) + 2)]
    lab = lambda v: "0" if v == 0 else (f"{v / 1e6:g} Mn".replace(".", ",") if v >= 1e6 else f"{v / 1e3:g} bin")
    return vals, [lab(v) for v in vals]


def _week_label(ts: pd.Timestamp) -> str:
    return f"{ts.day} {MONTHS_TR_SHORT[ts.month - 1]}"


def _add_forecast(fig: go.Figure, x: list, y_anchor: float, bridge: pd.DataFrame, fc: pd.DataFrame,
                  fmt=fmt_tl) -> None:
    """Tahmin çizgisi ve %80 aralığı. Çizgi son tam haftadan başlar, kısmi 28 Aralık haftasından
    (köprü) geçerek ufka bağlanır; böylece gerçekleşen ile tahmin arasında boşluk kalmaz.
    x: [son tam hafta, köprü haftası, ufuk haftaları...]"""
    full = pd.concat([bridge, fc])
    xb = x[1:]
    fig.add_trace(go.Scatter(x=xb + xb[::-1], y=list(full["hi"]) + list(full["lo"])[::-1], fill="toself", mode="lines",
                             fillcolor=rgba(PRIMARY, 0.15), line=dict(width=0), hoverinfo="skip", name="%80 aralık"))
    labels = ["28 Ara haftası (köprü, toplamlara katılmaz)"] + [f"{_week_label(t)} haftası" for t in fc.index]
    fig.add_trace(go.Scatter(x=x, y=[y_anchor] + list(full["point"]), mode="lines+markers",
                             line=dict(color=PRIMARY_DARK, width=2, dash="dot"), marker=dict(size=4), name="Tahmin",
                             customdata=[["", "", "", ""]] + [[lb, fmt(p), fmt(lo), fmt(hi)] for lb, p, lo, hi in
                                                             zip(labels, full["point"], full["lo"], full["hi"])],
                             hovertemplate="%{customdata[0]} (tahmin)<br><b>%{customdata[1]}</b><br>"
                                           "%80 aralık: %{customdata[2]} – %{customdata[3]}<extra></extra>"))


def period_trend(cur: pd.Series, prev: pd.Series | None, cur_name: str, prev_name: str | None,
                 days: pd.Series | None = None, forecast: pd.DataFrame | None = None,
                 bridge: pd.DataFrame | None = None) -> go.Figure:
    """Seçili dönemin haftalık cirosu. Kısmi haftalar (dönem ya da veri sınırında 7 günden az) içi boş
    nokta olarak gösterilir. Tahmin varsa 21 Aralık'tan köprü haftası üzerinden ufka bağlanır;
    yoksa önceki dönem aynı hafta sırasıyla kesikli çizgiyle gösterilir."""
    x = list(range(len(cur)))
    labels = [_week_label(t) for t in cur.index]
    days = days if days is not None else pd.Series(7, index=cur.index)
    full = (days >= 7).values
    if forecast is not None:
        prev = None  # tahmin varken grafik sade kalsın
    fig = go.Figure()
    if prev is not None and len(prev):
        pv = list(prev.values[: len(cur)])
        fig.add_trace(go.Scatter(x=x[: len(pv)], y=pv, mode="lines", line=dict(color=COMPARE, width=1.75, dash="dash"),
                                 name=prev_name, customdata=[fmt_tl(v) for v in pv],
                                 hovertemplate=f"{prev_name}<br><b>%{{customdata}}</b><extra></extra>"))
    xf = [xi for xi, ok in zip(x, full) if ok]
    yf = [v for v, ok in zip(cur.values, full) if ok]
    fig.add_trace(go.Scatter(x=xf, y=yf, mode="lines+markers", line=dict(color=PRIMARY, width=2.25),
                             marker=dict(size=5), fill="tozeroy", fillcolor=rgba(PRIMARY, 0.12), name=cur_name,
                             customdata=[[lb, fmt_tl(v)] for lb, v, ok in zip(labels, cur.values, full) if ok],
                             hovertemplate="%{customdata[0]} haftası<br><b>%{customdata[1]}</b><extra></extra>"))
    if (~full).any():
        xp = [xi for xi, ok in zip(x, full) if not ok]
        fig.add_trace(go.Scatter(x=xp, y=cur.values[~full], mode="markers", name="Kısmi hafta",
                                 marker=dict(symbol="circle-open", size=9, color=PRIMARY, line=dict(width=2)),
                                 customdata=[[lb, fmt_tl(v), int(d)] for lb, v, d, ok in zip(labels, cur.values, days, full) if not ok],
                                 hovertemplate="%{customdata[0]} haftası (kısmi, %{customdata[2]} gün)<br>"
                                               "<b>%{customdata[1]}</b><extra></extra>"))
    if forecast is not None and bridge is not None and xf:
        x_bridge = x[-1] if not full[-1] else x[-1] + 1
        fx = list(range(x_bridge + 1, x_bridge + 1 + len(forecast)))
        _add_forecast(fig, [xf[-1], x_bridge] + fx, yf[-1], bridge, forecast)
        if x_bridge > x[-1]:
            labels.append("28 Ara")
        x, labels = list(range(len(labels))) + fx, labels + [_week_label(t) for t in forecast.index]
    step = max(1, len(x) // 7)
    fig.update_xaxes(tickvals=x[::step], ticktext=labels[::step], range=[-0.5, x[-1] + 0.5])  # kısmi haftalar da görünsün
    vmax = max(cur.max(), prev.max() if prev is not None and len(prev) else 0,
               forecast["hi"].max() if forecast is not None else 0)
    tv, tt = _tl_ticks(vmax)
    fig.update_yaxes(tickvals=tv, ticktext=tt, range=[0, tv[-1]])
    fig = apply_style(fig, 200)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)))
    return fig


def segment_bars(seg: pd.DataFrame, highlight: tuple = ()) -> go.Figure:
    """Segment başına ciro payı (bordo) ve müşteri payı (açık); seçili segmentler vurgulu."""
    names = list(seg.index)[::-1]
    s = seg.loc[names]
    op = [1.0 if (not highlight or n in highlight) else 0.35 for n in names]
    share = lambda v: "%0,1’den az" if 0 < v < 0.001 else fmt_pct(v)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=s["customer_share"], orientation="h", marker=dict(color=PRIMARY_LIGHT, opacity=op),
                         text=[f"{fmt_pct(v)} ({int(n)})" for v, n in zip(s["customer_share"], s["customers"])],
                         textposition="outside", name="Müşteri payı", hovertemplate="%{y}<br>Müşteri payı: %{text}<extra></extra>"))
    fig.add_trace(go.Bar(y=names, x=s["revenue_share"], orientation="h", marker=dict(color=PRIMARY, opacity=op),
                         text=[share(v) for v in s["revenue_share"]], textposition="outside", name="Ciro payı",
                         hovertemplate="%{y}<br>Ciro payı: %{text}<extra></extra>"))
    fig.update_xaxes(visible=False, range=[0, 1.3])
    fig.update_yaxes(showgrid=False, ticksuffix="  ")
    fig.update_traces(cliponaxis=False, textfont=dict(size=11))
    fig = apply_style(fig, 200)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, showlegend=True,
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, traceorder="reversed", font=dict(size=11)))
    return fig


def quarter_bars(q: pd.Series, highlight: list[int]) -> go.Figure:
    colors = [PRIMARY if i in highlight else SECONDARY for i in q.index]
    fig = go.Figure(go.Bar(x=[f"{i}. Ç" for i in q.index], y=q.values, marker=dict(color=colors),
                           text=[fmt_tl(v) for v in q.values], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}<br><b>%{text}</b><extra></extra>"))
    fig.update_yaxes(visible=False, range=[0, q.max() * 1.25 if q.max() else 1])
    return apply_style(fig, 145)


def movers_bars(m: pd.DataFrame) -> go.Figure:
    """Önceki döneme göre en çok artan (yeşil) ve azalan (mercan) kategoriler.
    Çubuk uzunluğu değişimin büyüklüğü; yön renk ve işaretle gösterilir (çubuklar sola hizalı kalır)."""
    m = m.iloc[::-1]
    short = [n if len(n) <= 26 else n[:25].rstrip() + "…" for n in m.index]
    sign = lambda v: "+" if v > 0 else "−"
    txt = [f"{sign(d)}{fmt_tl(abs(d))}" + (f" ({sign(d)}{fmt_pct(abs(p))})" if pd.notna(p) else "") for d, p in zip(m["diff"], m["pct"])]
    fig = go.Figure(go.Bar(y=short, x=m["diff"].abs(), orientation="h",
                           marker=dict(color=[ACCENT if d > 0 else "#F07C80" for d in m["diff"]]),
                           text=txt, textposition="outside", cliponaxis=False, customdata=list(m.index),
                           hovertemplate="%{customdata}<br><b>%{text}</b><extra></extra>"))
    fig.update_xaxes(visible=False, range=[0, m["diff"].abs().max() * 1.9])
    fig.update_yaxes(showgrid=False, ticksuffix="  ")
    return apply_style(fig, 145)


def customer_waterfall(flow: dict, prev_name: str, cur_name: str) -> go.Figure:
    """Önceki dönemden seçili döneme müşteri sayısının değişimi."""
    fig = go.Figure(go.Waterfall(
        x=[prev_name, "Hareketsiz", "Geri dönen", "Yeni", cur_name],
        measure=["absolute", "relative", "relative", "relative", "total"],
        y=[flow["prev"], -flow["inactive"], flow["back"], flow["new"], flow["cur"]],
        text=[f"{flow['prev']:,}".replace(",", "."), f"−{flow['inactive']}", f"+{flow['back']}", f"+{flow['new']}",
              f"{flow['cur']:,}".replace(",", ".")],
        textposition="outside", cliponaxis=False, connector=dict(line=dict(color=MUTED, dash="dot", width=1)),
        decreasing=dict(marker=dict(color="#F07C80")), increasing=dict(marker=dict(color=ACCENT)),
        totals=dict(marker=dict(color=PRIMARY)), hoverinfo="skip"))
    fig.update_yaxes(visible=False, range=[0, max(flow["prev"], flow["cur"]) * 1.2])
    return apply_style(fig, 280)


def simple_bars(labels: list[str], values: list[float], texts: list[str], highlight: list[int] = (),
                height: int = 230) -> go.Figure:
    """Sade sütun grafik; vurgulanan sütunlar bordo, diğerleri lila."""
    fig = go.Figure(go.Bar(x=labels, y=values, text=texts, textposition="outside", cliponaxis=False,
                           marker=dict(color=[PRIMARY if i in highlight else SECONDARY for i in range(len(values))]),
                           hovertemplate="%{x}<br><b>%{text}</b><extra></extra>"))
    fig.update_yaxes(visible=False, range=[0, max(values) * 1.3 if max(values) else 1])
    fig.update_traces(textfont=dict(size=12, color=TEXT))
    return apply_style(fig, height)


def forecast_chart(r: dict, unit: str) -> go.Figure:
    """Tüm yılın haftalık serisi, düzeltilen haftalar, doğrulama dönemleri ve tahmin."""
    s, fc, bridge = r["series"], r["forecast"], r["bridge"]
    fmt = fmt_tl if unit == "TL" else (lambda v: f"{v:,.0f} adet".replace(",", "."))
    end = s.index[-1] + pd.Timedelta(days=6)
    fig = go.Figure()
    for x0, x1, color, alpha, text in [(PANDEMIC_BAND[0], PANDEMIC_BAND[1], COMPARE, 0.10, "Pandemi kısıtlamaları"),
                                       (r["cv_start"], r["test_start"], SECONDARY, 0.30, "Kayan doğrulama"),
                                       (r["test_start"], end, SECONDARY, 0.55, "Son test")]:
        fig.add_vrect(x0=x0, x1=x1, fillcolor=rgba(color, alpha), line_width=0, layer="below", annotation_text=text,
                      annotation_position="top left", annotation_font=dict(size=11, color=MUTED))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=PRIMARY, width=2.25), name="Gerçekleşen",
                             fill="tozeroy", fillcolor=rgba(PRIMARY, 0.08), customdata=[fmt(v) for v in s.values],
                             hovertemplate="%{x|%d.%m.%Y} haftası<br><b>%{customdata}</b><extra></extra>"))
    for mask, name, symbol in [(r["filled"], "Doldurulan hafta (kayıt boşluğu)", "square-open"),
                               (r["capped"], "Sınırlanan hafta (pandemi)", "circle-open")]:
        idx = mask[mask].index
        if len(idx):
            fig.add_trace(go.Scatter(x=idx, y=r["clean"][idx], mode="markers", name=name,
                                     marker=dict(symbol=symbol, size=9, color=PRIMARY_DARK, line=dict(width=2)),
                                     customdata=[[fmt(a), fmt(b)] for a, b in zip(s[idx], r["clean"][idx])],
                                     hovertemplate="%{x|%d.%m.%Y} haftası<br>Gerçek: %{customdata[0]}<br>"
                                                   "Modelde kullanılan: %{customdata[1]}<extra></extra>"))
    partial = r.get("partial_last")
    if partial is not None:
        fig.add_trace(go.Scatter(x=[partial[0]], y=[partial[1]], mode="markers", name="Kısmi hafta (28–31 Ara)",
                                 marker=dict(symbol="diamond-open", size=9, color=PRIMARY, line=dict(width=2)),
                                 customdata=[[fmt(partial[1]), partial[2]]],
                                 hovertemplate="28 Ara haftası (kısmi, %{customdata[1]} gün)<br><b>%{customdata[0]}</b><extra></extra>"))
    _add_forecast(fig, [s.index[-1], bridge.index[0]] + list(fc.index), s.iloc[-1], bridge, fc, fmt)
    months = pd.date_range("2020-01-01", fc.index[-1], freq="MS")
    fig.update_xaxes(tickvals=months, ticktext=[MONTHS_TR_SHORT[m.month - 1] + (" 2021" if m.year == 2021 and m.month == 1 else "")
                                                 for m in months])
    vmax = max(s.max(), fc["hi"].max(), bridge["hi"].max())
    if unit == "TL":
        tv, tt = _tl_ticks(vmax)
        fig.update_yaxes(tickvals=tv, ticktext=tt, range=[0, tv[-1]])
    else:
        fig.update_yaxes(tickformat=",.0f", rangemode="tozero")
    fig = apply_style(fig, 300)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)))
    return fig

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
    fig.update_xaxes(showgrid=False, linecolor=LINE, ticks="", tickfont=dict(color=MUTED), automargin=True, fixedrange=True)
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


def _add_forecast(fig: go.Figure, x: list, fc: pd.DataFrame) -> None:
    """Tahmin çizgisi ve %80 aralık bandı."""
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(fc["hi"]) + list(fc["lo"])[::-1], fill="toself", mode="lines",
                             fillcolor=rgba(PRIMARY, 0.15), line=dict(width=0), hoverinfo="skip", name="%80 aralık"))
    fig.add_trace(go.Scatter(x=x, y=fc["point"], mode="lines+markers", line=dict(color=PRIMARY_DARK, width=2, dash="dot"),
                             marker=dict(size=4), name="Tahmin",
                             customdata=list(zip([_week_label(t) for t in fc.index], [fmt_tl(v) for v in fc["point"]],
                                                 [fmt_tl(v) for v in fc["lo"]], [fmt_tl(v) for v in fc["hi"]])),
                             hovertemplate="%{customdata[0]} haftası (tahmin)<br><b>%{customdata[1]}</b><br>"
                                           "%80 aralık: %{customdata[2]} – %{customdata[3]}<extra></extra>"))


def period_trend(cur: pd.Series, prev: pd.Series | None, cur_name: str, prev_name: str | None,
                 forecast: pd.DataFrame | None = None) -> go.Figure:
    """Seçili dönemin haftalık cirosu; tahmin yoksa önceki dönem aynı hafta sırasıyla kesikli çizgi."""
    x = list(range(len(cur)))
    labels = [_week_label(t) for t in cur.index]
    if forecast is not None:
        prev = None  # tahmin varken grafik sade kalsın
    fig = go.Figure()
    if prev is not None and len(prev):
        pv = list(prev.values[: len(cur)])
        fig.add_trace(go.Scatter(x=x[: len(pv)], y=pv, mode="lines", line=dict(color=COMPARE, width=1.75, dash="dash"),
                                 name=prev_name, customdata=[fmt_tl(v) for v in pv],
                                 hovertemplate=f"{prev_name}<br><b>%{{customdata}}</b><extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=cur.values, mode="lines+markers", line=dict(color=PRIMARY, width=2.25),
                             marker=dict(size=5), fill="tozeroy", fillcolor=rgba(PRIMARY, 0.12), name=cur_name,
                             customdata=list(zip(labels, [fmt_tl(v) for v in cur.values])),
                             hovertemplate="%{customdata[0]} haftası<br><b>%{customdata[1]}</b><extra></extra>"))
    if forecast is not None:
        fx = list(range(len(cur), len(cur) + len(forecast)))
        _add_forecast(fig, fx, forecast)
        x, labels = x + fx, labels + [_week_label(t) for t in forecast.index]
    step = max(1, len(x) // 7)
    fig.update_xaxes(tickvals=x[::step], ticktext=labels[::step])
    vmax = max(cur.max(), prev.max() if prev is not None and len(prev) else 0,
               forecast["hi"].max() if forecast is not None else 0)
    tv, tt = _tl_ticks(vmax)
    fig.update_yaxes(tickvals=tv, ticktext=tt, range=[0, tv[-1]])
    fig = apply_style(fig, 200)
    fig.update_layout(showlegend=prev is not None or forecast is not None,
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)))
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
        x=[prev_name, "Kaybedilen", "Geri dönen", "Yeni", cur_name],
        measure=["absolute", "relative", "relative", "relative", "total"],
        y=[flow["prev"], -flow["lost"], flow["back"], flow["new"], flow["cur"]],
        text=[f"{flow['prev']:,}".replace(",", "."), f"−{flow['lost']}", f"+{flow['back']}", f"+{flow['new']}",
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
    """Tüm yılın haftalık serisi, sınırlanan aykırı haftalar, doğrulama dönemi ve tahmin."""
    s, fc = r["series"], r["forecast"]
    fmt = fmt_tl if unit == "TL" else (lambda v: f"{v:,.0f} adet".replace(",", "."))
    fig = go.Figure()
    fig.add_vrect(x0=PANDEMIC_BAND[0], x1=PANDEMIC_BAND[1], fillcolor=rgba(COMPARE, 0.10), line_width=0, layer="below",
                  annotation_text="Pandemi kısıtlamaları", annotation_position="top left", annotation_font=dict(size=11, color=MUTED))
    fig.add_vrect(x0=r["holdout_start"], x1=s.index[-1] + pd.Timedelta(days=6), fillcolor=rgba(SECONDARY, 0.35), line_width=0,
                  layer="below", annotation_text="Doğrulama", annotation_position="top left", annotation_font=dict(size=11, color=MUTED))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=PRIMARY, width=2.25), name="Gerçekleşen",
                             fill="tozeroy", fillcolor=rgba(PRIMARY, 0.08), customdata=[fmt(v) for v in s.values],
                             hovertemplate="%{x|%d.%m.%Y} haftası<br><b>%{customdata}</b><extra></extra>"))
    flagged = r["flagged"][r["flagged"]].index
    if len(flagged):
        fig.add_trace(go.Scatter(x=flagged, y=r["clean"][flagged], mode="markers", name="Sınırlanan değer",
                                 marker=dict(symbol="circle-open", size=9, color=PRIMARY_DARK, line=dict(width=2)),
                                 customdata=list(zip([fmt(v) for v in s[flagged]], [fmt(v) for v in r["clean"][flagged]])),
                                 hovertemplate="%{x|%d.%m.%Y} haftası<br>Gerçek: %{customdata[0]}<br>"
                                               "Modelde kullanılan: %{customdata[1]}<extra></extra>"))
    x = list(fc.index)
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(fc["hi"]) + list(fc["lo"])[::-1], fill="toself", mode="lines",
                             fillcolor=rgba(PRIMARY, 0.15), line=dict(width=0), hoverinfo="skip", name="%80 aralık"))
    fig.add_trace(go.Scatter(x=x, y=fc["point"], mode="lines+markers", line=dict(color=PRIMARY_DARK, width=2, dash="dot"),
                             marker=dict(size=4), name="Tahmin",
                             customdata=list(zip([fmt(v) for v in fc["point"]], [fmt(v) for v in fc["lo"]], [fmt(v) for v in fc["hi"]])),
                             hovertemplate="%{x|%d.%m.%Y} haftası (tahmin)<br><b>%{customdata[0]}</b><br>"
                                           "%80 aralık: %{customdata[1]} – %{customdata[2]}<extra></extra>"))
    months = pd.date_range("2020-01-01", fc.index[-1], freq="MS")
    fig.update_xaxes(tickvals=months, ticktext=[MONTHS_TR_SHORT[m.month - 1] + (" 2021" if m.year == 2021 and m.month == 1 else "")
                                                 for m in months])
    vmax = max(s.max(), fc["hi"].max())
    if unit == "TL":
        tv, tt = _tl_ticks(vmax)
        fig.update_yaxes(tickvals=tv, ticktext=tt, range=[0, tv[-1]])
    else:
        fig.update_yaxes(tickformat=",.0f", rangemode="tozero")
    fig = apply_style(fig, 300)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11)))
    return fig

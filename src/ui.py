"""Tekrar kullanılan arayüz parçaları: bölüm başlığı, KPI kartı, aksiyon kartları.

Sayfa bağlantıları için her zaman st.page_link kullanılır: normal bir HTML
bağlantısı sayfayı yeniden yükler ve filtre seçimleri kaybolur.
"""

import re

import streamlit as st

from src.actions import Action
from src.chat import add_fact
from src.config import KPI_TINTS
from src.formatting import fmt_pct

DOTS = [t[2] for t in KPI_TINTS]


def section_header(title: str, badge: str | None = None) -> None:
    """Bölüm başlığı ve isteğe bağlı filtre etiketi; tüm başlıklar aynı yükseklikte."""
    bdg = f'<span class="bdg">{badge}</span>' if badge else ""
    st.markdown(f'<div class="sec-head"><h3>{title}</h3>{bdg}</div>', unsafe_allow_html=True)


def panel_link(page: str, label: str) -> None:
    """Panelin altında, sağa yaslı ayrıntı bağlantısı."""
    with st.container(key=f"plink_{label}_{page}".replace("/", "_").replace(".", "_").replace(" ", "_")):
        st.page_link(page, label=f"{label} →")


def kpi_card(i: int, label: str, value: str, change: float | None = None, comp: str = "", prev_text: str = "",
             page: str | None = None, inverse: bool = False, note: str | None = None) -> None:
    """change: önceki döneme göre oran (ör. 0.444); None ise karşılaştırma yoktur. note verilirse onu gösterir."""
    if note is not None:
        delta = f'<span class="muted">{note}</span>'
    elif change is None:
        delta = '<span class="muted">Karşılaştırma için önceki dönem verisi yok</span>'
    else:
        good = (change >= 0) != inverse
        delta = (f'<span class="{"up" if good else "down"}">{"▲" if change >= 0 else "▼"} {fmt_pct(abs(change))}</span>'
                 f'<span class="muted"> {comp} ({prev_text})</span>')
    add_fact(f"{label}: {value}" + (f" ({re.sub('<[^>]+>', '', delta)})" if change is not None or note else ""))
    with st.container(key=f"kpi_{i}"):
        st.markdown(f'<div class="kpi-label"><span class="dot" style="background:{DOTS[i % 4]}"></span>{label}</div>'
                    f'<div class="kpi-value">{value}</div><div class="kpi-delta">{delta}</div>', unsafe_allow_html=True)
        if page:
            st.page_link(page, label="Ayrıntı →")


def action_cards(actions: list[Action], note: str | None = None) -> None:
    head, rules = st.columns([3, 1], vertical_alignment="center")
    head.markdown('<div class="sec-head"><h3>Önerilen aksiyonlar</h3></div>', unsafe_allow_html=True)
    rules.page_link("app_pages/veri_notlari.py", label="Kurallar")
    if not actions:
        st.caption("Seçili filtrelerde tetiklenen öneri yok.")
    for a in actions[:3]:
        add_fact(f"Önerilen aksiyon ({a.dept}{', tahmine dayalı' if a.forecast else ''}): {a.title}. {a.evidence}")
    for i, a in enumerate(actions[:3]):
        chips = f'<span class="chip dept-{a.dept}">{a.dept}</span>' + ('<span class="chip fc">Tahmine dayalı</span>' if a.forecast else "")
        with st.container(key=f"act_{i}"):
            st.markdown(f'<div class="chips">{chips}</div><div class="act-title">{a.title}</div>'
                        f'<div class="act-ev">{a.evidence}</div>', unsafe_allow_html=True)
            st.page_link(a.page, label=f"{a.link} →")
    if note:
        st.caption(note)


def html_table(headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> None:
    """Türkçe biçimlendirilmiş değerlerle sade tablo (st.dataframe Türkçe sayı biçimi desteklemiyor)."""
    align = align or ["left"] * len(headers)
    th = "".join(f'<th style="text-align:{a}">{h}</th>' for h, a in zip(headers, align))
    body = "".join("<tr>" + "".join(f'<td style="text-align:{a}">{c}</td>' for c, a in zip(r, align)) + "</tr>" for r in rows)
    st.markdown(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def bar_cell(value: float, max_value: float, text: str) -> str:
    """Tablo hücresi içinde küçük yatay çubuk."""
    w = 0 if not max_value else max(3, value / max_value * 80)
    return f'<span class="cell-bar"><span style="width:{w:.0f}px"></span></span> {text}'

"""Tekrar kullanılan arayüz parçaları: bölüm başlığı, KPI kartı, aksiyon kartları, sekmeler.

Sayfa bağlantıları için her zaman st.page_link kullanılır: normal bir HTML bağlantısı sayfayı
yeniden yükler ve filtre seçimleri kaybolur. Bağlantı belirli bir sekmeyi açacaksa sekme adı
adres parametresi (?sekme=...) olarak gönderilir; hedef sayfa page_tabs ile bu sekmeyi seçer.
"""

import streamlit as st

from src.actions import Action
from src.config import KPI_TINTS, PAGE_NOTES, TAB_PARAM
from src.formatting import fmt_pct, tr_title

DOTS = [t[2] for t in KPI_TINTS]


def _link(page: str, label: str, tab: str | None = None) -> None:
    st.page_link(page, label=label, query_params={TAB_PARAM: tab} if tab else None)


def page_tabs(names: list[str], key: str):
    """Sekmeler; adres parametresinde geçerli bir sekme adı varsa o sekme seçili açılır."""
    target = st.query_params.get(TAB_PARAM)
    if target in names:
        st.session_state[key] = target
        del st.query_params[TAB_PARAM]  # sonraki sekme seçimlerini ezmesin
    return st.tabs(names, key=key, on_change="rerun")


def section_header(title: str, badge: str | list[str] | None = None) -> None:
    """Bölüm başlığı (her kelime büyük harfle) ve isteğe bağlı etiketler; tüm başlıklar aynı yükseklikte."""
    badges = [badge] if isinstance(badge, str) else (badge or [])
    bdg = "".join(f'<span class="bdg">{b}</span>' for b in badges)
    st.markdown(f'<div class="sec-head"><h3>{tr_title(title)}</h3>{bdg}</div>', unsafe_allow_html=True)


def panel_link(page: str, label: str, tab: str | None = None) -> None:
    """Panelin altında, sağa yaslı ayrıntı bağlantısı."""
    with st.container(key=f"plink_{label}_{page}".replace("/", "_").replace(".", "_").replace(" ", "_")):
        _link(page, f"{label} →", tab)


def kpi_card(i: int, label: str, value: str, change: float | None = None, comp: str = "", prev_text: str = "",
             page: str | None = None, inverse: bool = False, note: str | None = None, tab: str | None = None) -> None:
    """change: önceki döneme göre oran (ör. 0.444); None ise karşılaştırma yoktur. note verilirse onu gösterir."""
    if note is not None:
        delta = f'<span class="muted">{note}</span>'
    elif change is None:
        delta = '<span class="muted">Karşılaştırma için önceki dönem verisi yok</span>'
    else:
        good = (change >= 0) != inverse
        delta = (f'<span class="{"up" if good else "down"}">{"▲" if change >= 0 else "▼"} {fmt_pct(abs(change))}</span>'
                 f'<span class="muted"> {comp} ({prev_text})</span>')
    with st.container(key=f"kpi_{i}"):
        st.markdown(f'<div class="kpi-label"><span class="dot" style="background:{DOTS[i % 4]}"></span>{tr_title(label)}</div>'
                    f'<div class="kpi-value">{value}</div><div class="kpi-delta">{delta}</div>', unsafe_allow_html=True)
        if page:
            _link(page, "Ayrıntı →", tab)


def action_cards(actions: list[Action], note: str | None = None, limit: int = 3) -> None:
    head, rules = st.columns([3, 1], vertical_alignment="center")
    head.markdown('<div class="sec-head"><h3>Önerilen Aksiyonlar</h3></div>', unsafe_allow_html=True)
    with rules:
        _link(PAGE_NOTES, "Kurallar", "Aksiyon Kuralları")
    if not actions:
        st.caption("Seçili filtrelerde tetiklenen öneri yok.")
    for i, a in enumerate(actions[:limit]):
        chips = f'<span class="chip dept-{a.dept}">{a.dept}</span>' + ('<span class="chip fc">Tahmine dayalı</span>' if a.forecast else "")
        with st.container(key=f"act_{i}"):
            st.markdown(f'<div class="chips">{chips}</div><div class="act-title">{a.title}</div>'
                        f'<div class="act-ev">{a.evidence}</div>', unsafe_allow_html=True)
            _link(a.page, f"{a.link} →", a.tab)
    if note:
        st.caption(note)


def html_table(headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> None:
    """Türkçe biçimlendirilmiş değerlerle sade tablo (st.dataframe Türkçe sayı biçimi desteklemiyor).
    Sütun başlıkları başlık düzeninde (her kelime büyük harfle) yazılır."""
    align = align or ["left"] * len(headers)
    th = "".join(f'<th style="text-align:{a}">{tr_title(h)}</th>' for h, a in zip(headers, align))
    body = "".join("<tr>" + "".join(f'<td style="text-align:{a}">{c}</td>' for c, a in zip(r, align)) + "</tr>" for r in rows)
    st.markdown(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def bar_cell(value: float, max_value: float, text: str) -> str:
    """Tablo hücresi içinde küçük yatay çubuk."""
    w = 0 if not max_value else max(3, value / max_value * 80)
    return f'<span class="cell-bar"><span style="width:{w:.0f}px"></span></span> {text}'


def segment_period_note(f, data_end) -> None:
    """Segmentler yıl sonu verisiyle belirlendiği için geçmiş dönemlerde uyarı gösterir."""
    if f.end < data_end:
        st.caption("Segmentler 2020 yıl sonu davranışına göre belirlendi; seçili dönemde müşterinin o günkü "
                   "davranışını yansıtmayabilir (ör. yıl sonunda uykudaki bir müşteri bu dönemde aktif olabilir).")

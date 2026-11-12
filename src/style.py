"""Tema dosyasının yapamadığı görsel ayarlar: üst çubuk, sabit filtre çubuğu, KPI ve
aksiyon kartları, tablolar ve sağ alttaki sohbet düğmesi. Renkler src/config.py'den gelir."""

import streamlit as st

from src.config import (BUTTON_RED, GREEN, HEADER_BG, KPI_TINTS, LINE, MUTED, PRIMARY, PRIMARY_DARK, RED,
                        SURFACE, TEXT, rgba)

KPI_CSS = "\n".join(f".st-key-kpi_{i} {{ background: linear-gradient(135deg, {a}, {b}); }}"
                    for i, (a, b, _) in enumerate(KPI_TINTS))

_CSS = f"""
<style>
/* Üst gezinme çubuğu */
[data-testid="stHeader"] {{ background: {HEADER_BG}; border-bottom: 1px solid {LINE}; }}
[data-testid="stHeaderLogo"] {{ height: 1.7rem; max-width: 12rem; }}
[data-testid="stTopNavLink"] {{ background: transparent !important; border-radius: 0; border-bottom: 3px solid transparent; }}
[data-testid="stTopNavLink"] p {{ color: {TEXT} !important; font-weight: 500; }}
[data-testid="stTopNavLink"]:hover p {{ color: {PRIMARY_DARK} !important; }}
[data-testid="stTopNavLink"][aria-current="page"] {{ border-bottom: 3px solid {PRIMARY}; }}
[data-testid="stTopNavLink"][aria-current="page"] p {{ color: {PRIMARY_DARK} !important; font-weight: 700; }}
[data-testid="stMainMenuButton"] svg {{ color: {TEXT}; }}
[data-testid="stMainBlockContainer"] {{ padding: 3.75rem 1.5rem 1rem; max-width: 100%; }}
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] {{ gap: .7rem; }}

/* Sabit filtre çubuğu (açık ya da gizli) */
.st-key-filter_bar, .st-key-filter_bar_min {{ position: sticky; top: 3.75rem; z-index: 50;
  background: {SURFACE}; padding: .45rem 1.5rem; margin: -1rem -1.5rem 0;
  width: calc(100% + 3rem) !important; max-width: none !important; border-bottom: 1px solid {LINE}; }}
.st-key-filter_bar_min {{ padding: .35rem 1.5rem; }}
.st-key-filter_bar [data-baseweb="select"] > div, .st-key-filter_bar [data-baseweb="input"] {{ min-height: 2.1rem; background: #FFFFFF; }}
.st-key-filter_bar [data-baseweb="select"] > div > div {{ padding-top: 0; padding-bottom: 0; }}
.st-key-filter_bar input {{ padding-top: .3rem; padding-bottom: .3rem; font-size: .85rem; }}
.st-key-filter_bar button {{ min-height: 2.1rem; padding-top: .2rem; padding-bottom: .2rem; }}
.st-key-filter_bar [data-baseweb="select"] span, .st-key-filter_bar [data-baseweb="select"] div {{ font-size: .85rem; }}
.fb-min {{ font-size: .8rem; color: {PRIMARY_DARK}; }}
.st-key-filter_bar_min button {{ min-height: 2rem; padding: .15rem .7rem; }}
.st-key-filter_bar_min button p, .st-key-filter_bar button p {{ font-size: .82rem; }}

/* Bölüm panelleri: ince "hayalet" çizgilerle gruplama */
[class*="st-key-panel_"] {{ border: 1px solid rgba(47,43,44,.08); border-radius: 16px; padding: .65rem .9rem .4rem; gap: .35rem; height: 100%; }}
/* Aynı satırdaki paneller eşit yükseklikte olsun */
[data-testid="stColumn"]:has([class*="st-key-panel_"]) > [data-testid="stVerticalBlock"],
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-panel_"]) {{ height: 100%; }}
[class*="st-key-plink_"] {{ margin-top: auto; align-items: flex-end; }}
.sec-head {{ min-height: 1.9rem; }}

/* Başlıklar ve etiketler */
h1 {{ font-size: 1.75rem !important; padding: 0 !important; letter-spacing: -.02em; }}
.sec-head {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }}
.sec-head h3 {{ font-size: 1.15rem !important; margin: 0; padding: 0 !important; letter-spacing: -.01em; }}
.bdg {{ background: #F4EDF7; color: {MUTED}; border-radius: 11px; padding: 2px 9px; font-size: .7rem; font-weight: 600; white-space: nowrap; }}
.muted {{ color: {MUTED}; }}

/* KPI kartları: her biri paletten yumuşak bir geçiş */
[class*="st-key-kpi_"] {{ border-radius: 16px; padding: 1rem 1.2rem .85rem; gap: .2rem; min-height: 7.6rem; justify-content: flex-start; }}
{KPI_CSS}
.kpi-label {{ font-size: .82rem; font-weight: 600; display: flex; align-items: center; gap: .5rem; }}
.dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
.kpi-value {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.75rem; margin: .15rem 0; font-weight: 600; letter-spacing: -.02em; line-height: 1.25; }}
.kpi-delta {{ font-size: .8rem; margin-bottom: .5rem; }}
.up {{ color: {GREEN}; font-weight: 700; }} .down {{ color: {RED}; font-weight: 700; }}

/* Sayfa bağlantılarını sade metin bağlantısına çevir */
[data-testid="stPageLink"] a {{ padding: 0; min-height: 1.6rem; background: transparent !important; }}
[data-testid="stPageLink"] p {{ color: {PRIMARY_DARK}; font-weight: 700; font-size: .82rem; }}

/* Aksiyon kartları */
[class*="st-key-act_"] {{ border: 1px solid {LINE}; border-radius: 14px; padding: .6rem .85rem .3rem; gap: .2rem; background: #FFFFFF; }}
.chips {{ display: flex; gap: .35rem; flex-wrap: wrap; }}
.chip {{ font-size: .68rem; font-weight: 700; border-radius: 11px; padding: 2px 8px; }}
.dept-Satış {{ background: #FFE3E4; color: #B3161B; }} .dept-Pazarlama {{ background: #F1E4F8; color: #6B3480; }}
.dept-Tedarik {{ background: #F4EDF7; color: #5B4A63; }} .dept-Yönetim {{ background: #FAEAFF; color: #6B3480; }}
.dept-Veri {{ background: #EFEAF2; color: {TEXT}; }} .chip.fc {{ background: #FFF1D6; color: #7A4A06; }}
.act-title {{ font-weight: 700; font-size: .88rem; line-height: 1.35; }}
.act-ev {{ font-size: .8rem; color: {MUTED}; line-height: 1.4; margin-bottom: .5rem; }}

/* Tablolar ve hücre içi göstergeler */
.tbl {{ overflow-x: auto; border-radius: 10px; }}
.tbl table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
.tbl th {{ background: {SURFACE}; color: {PRIMARY_DARK}; font-size: .75rem; font-weight: 700; padding: .45rem .7rem; white-space: nowrap; border: none; }}
.tbl td {{ padding: .42rem .7rem; border: none; border-bottom: 1px solid {LINE}; font-variant-numeric: tabular-nums; }}
.heat {{ display: inline-block; min-width: 3.2rem; padding: 2px 8px; border-radius: 6px; }}
.cell-bar {{ display: inline-block; width: 80px; height: 8px; background: {LINE}; border-radius: 4px; vertical-align: middle; }}
.cell-bar span {{ display: block; height: 8px; background: {PRIMARY}; border-radius: 4px; }}
.abc {{ display: grid; grid-template-columns: minmax(90px, .6fr) repeat(3, minmax(130px, 1fr)); gap: 8px; }}
.abc .cell {{ border-radius: 12px; padding: .55rem .8rem; min-height: 5.2rem; }}
.abc .n {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.25rem; font-weight: 600; }}
.abc .s {{ font-size: .8rem; font-weight: 600; }} .abc .p {{ font-size: .75rem; }}
.abc .rh {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 700; color: {PRIMARY_DARK}; }}
.abc .ch {{ font-size: .85rem; font-weight: 700; }} .abc .sub {{ font-size: .72rem; color: {MUTED}; }}

/* Sekmeler */
[data-baseweb="tab-list"] button p {{ font-size: .92rem; font-weight: 600; }}

/* Sağ altta sabit sohbet düğmesi */
.st-key-chat_fab {{ position: fixed; right: 24px; bottom: 24px; z-index: 1000; width: auto !important; }}
.st-key-chat_fab button {{ background: {BUTTON_RED}; color: #FFFFFF; border: none;
  border-radius: 26px; height: 52px; padding: 0 22px; box-shadow: 0 8px 22px {rgba(PRIMARY, .35)}; }}
.st-key-chat_fab button p {{ color: #FFFFFF; font-weight: 700; font-size: .95rem; }}
.chat-ctx {{ background: {SURFACE}; color: {PRIMARY_DARK}; font-size: .78rem; padding: .4rem .6rem; border-radius: 8px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

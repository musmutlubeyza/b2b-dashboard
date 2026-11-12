"""Üstte sabit duran ortak filtre çubuğu ve filtre uygulama mantığı.

Filtreler ana dosyada (streamlit_app.py) çizilir; ana dosya her sayfa
geçişinde çalıştığı için seçimler sayfalar arasında korunur.
"""

import datetime as dt
from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from src.config import CUSTOM_PERIOD, DEFAULT_PERIOD, PERIODS, SEGMENTS
from src.data_loader import category_tree
from src.formatting import fmt_date, tr_sort_key

FIELDS = ("period", "dates", "cities", "categories", "subcategories", "segments")


def _w(name: str) -> str:  # widget anahtarı
    return f"w_{name}"


def _v(name: str) -> str:  # kalıcı değer anahtarı (widget çizilmese de silinmez)
    return f"fv_{name}"


@dataclass(frozen=True)
class Filters:
    period: str
    start: dt.date
    end: dt.date
    cities: tuple = ()
    categories: tuple = ()      # ana kategoriler
    segments: tuple = ()
    subcategories: tuple = ()   # standart alt kategoriler

    @property
    def is_quarter(self) -> bool:
        return self.period.endswith("Çeyrek 2020")


def _period_dates(period: str, lo: dt.date, hi: dt.date) -> tuple[dt.date, dt.date]:
    start, end = PERIODS[period]
    return max(start, lo), min(end, hi)


def _sync(name: str) -> None:
    """Widget değişince değeri kalıcı anahtara kopyalar."""
    st.session_state[_v(name)] = st.session_state[_w(name)]


def _on_period_change(lo, hi):
    _sync("period")
    p = st.session_state[_v("period")]
    if p != CUSTOM_PERIOD:
        st.session_state[_v("dates")] = _period_dates(p, lo, hi)


def _reset(lo, hi):
    st.session_state[_v("period")] = DEFAULT_PERIOD
    st.session_state[_v("dates")] = _period_dates(DEFAULT_PERIOD, lo, hi)
    for k in ("cities", "categories", "subcategories", "segments"):
        st.session_state[_v(k)] = []


def _toggle_open():
    st.session_state["filters_open"] = not st.session_state.get("filters_open", True)


def _current(lo: dt.date, hi: dt.date) -> Filters:
    ss = st.session_state
    period = ss[_v("period")]
    if period != CUSTOM_PERIOD:
        start, end = _period_dates(period, lo, hi)
    else:
        d = ss[_v("dates")]
        # Tarih seçici, aralık seçimi sürerken tek tarih döndürebilir
        if isinstance(d, (tuple, list)):
            start, end = (d[0], d[1]) if len(d) > 1 else (d[0], d[0])
        else:
            start = end = d
    return Filters(period, start, end, tuple(ss[_v("cities")]), tuple(ss[_v("categories")]), tuple(ss[_v("segments")]),
                   tuple(ss[_v("subcategories")]))


def _sub_options(tree: dict) -> list:
    """Alt kategori seçenekleri: ana kategori seçiliyse yalnızca onun alt kategorileri."""
    mains = st.session_state[_v("categories")] or list(tree)
    return sorted({s for m in mains for s in tree.get(m, [])}, key=tr_sort_key)


def _on_main_change(tree: dict):
    """Ana kategori değişince artık geçerli olmayan alt kategori seçimlerini bırakır."""
    _sync("categories")
    allowed = set(_sub_options(tree))
    st.session_state[_v("subcategories")] = [s for s in st.session_state[_v("subcategories")] if s in allowed]


@st.fragment
def _filter_fragment(cities: list, tree: dict, lo: dt.date, hi: dt.date, disabled: bool) -> None:
    """Filtre çubuğu ayrı bir parça (fragment): gizle/göster yalnızca bu parçayı yeniden çizer.
    Seçimler widget anahtarlarında değil, kalıcı 'fv_' anahtarlarında tutulur; widget çizilmediğinde
    Streamlit widget durumunu sildiği için bu ayrım gerekli."""
    if st.session_state.get("filters_open", True):
        subs = _sub_options(tree)
        st.session_state[_v("subcategories")] = [x for x in st.session_state[_v("subcategories")] if x in subs]
        for n in FIELDS:  # widget'ları kalıcı değerlerle başlat
            st.session_state[_w(n)] = st.session_state[_v(n)]
        with st.container(key="filter_bar"):
            cols = st.columns([0.95, 1.3, 0.85, 1.05, 1.1, 1.3, 0.62, 0.22], vertical_alignment="center")
            hidden = "collapsed"  # alanların içindeki değer ve yer tutucular ne işe yaradıklarını gösteriyor
            period = cols[0].selectbox("Dönem", list(PERIODS) + [CUSTOM_PERIOD], key=_w("period"),
                                       on_change=_on_period_change, args=(lo, hi), disabled=disabled,
                                       label_visibility=hidden)
            cols[1].date_input("Tarih aralığı", min_value=lo, max_value=hi, format="DD.MM.YYYY", key=_w("dates"),
                               on_change=_sync, args=("dates",), disabled=disabled or period != CUSTOM_PERIOD,
                               label_visibility=hidden)
            cols[2].multiselect("İl", cities, key=_w("cities"), on_change=_sync, args=("cities",),
                                placeholder="Tüm iller", disabled=disabled, label_visibility=hidden)
            cols[3].multiselect("Ana kategori", list(tree), key=_w("categories"), on_change=_on_main_change, args=(tree,),
                                placeholder="Tüm ana kategoriler", disabled=disabled, label_visibility=hidden)
            cols[4].multiselect("Alt kategori", subs, key=_w("subcategories"), on_change=_sync, args=("subcategories",),
                                placeholder="Tüm alt kategoriler", disabled=disabled, label_visibility=hidden)
            cols[5].multiselect("Müşteri segmenti", SEGMENTS, key=_w("segments"), on_change=_sync, args=("segments",),
                                placeholder="Tüm segmentler (yıl sonu)", disabled=disabled, label_visibility=hidden)
            cols[6].button("Temizle", icon=":material/restart_alt:", on_click=_reset, args=(lo, hi), disabled=disabled,
                           width="stretch", help="Tüm filtreleri varsayılana döndür")
            cols[7].button("", icon=":material/expand_less:", on_click=_toggle_open, key="filters_hide",
                           help="Filtreleri gizle")
            if disabled:
                st.caption("Bu sayfa filtrelerden etkilenmez; seçimler diğer sayfalar için korunur.")
    else:
        with st.container(key="filter_bar_min"):
            left, right = st.columns([8, 1.4], vertical_alignment="center")
            left.markdown(f'<div class="fb-min"><b>Filtreler:</b> {describe(_current(lo, hi))}</div>', unsafe_allow_html=True)
            right.button("Filtreleri göster", icon=":material/expand_more:", on_click=_toggle_open,
                         key="filters_show", width="stretch")

    f = _current(lo, hi)
    if "filters" not in st.session_state:
        st.session_state["filters"] = f
    elif f != st.session_state["filters"]:
        st.session_state["filters"] = f
        st.rerun(scope="app")  # yalnızca gerçek bir filtre değişikliğinde tüm sayfa yeniden çizilir


def render_filter_bar(df: pd.DataFrame, disabled: bool = False) -> Filters:
    """Filtre çubuğunu çizer (açık ya da gizli) ve seçimleri döndürür."""
    lo, hi = df["InvoiceDate"].min().date(), df["InvoiceDate"].max().date()
    if _v("period") not in st.session_state:
        _reset(lo, hi)
    _filter_fragment(sorted(df["City"].unique(), key=tr_sort_key), category_tree(), lo, hi, disabled)
    return st.session_state["filters"]


def apply_filters(df: pd.DataFrame, f: Filters, ignore: tuple = ()) -> pd.DataFrame:
    """Filtreleri uygular. ignore: yok sayılacak filtreler ('period', 'city', 'category', 'segment')."""
    mask = pd.Series(True, index=df.index)
    if "period" not in ignore:
        mask &= df["InvoiceDate"].between(pd.Timestamp(f.start), pd.Timestamp(f.end))
    if f.cities and "city" not in ignore:
        mask &= df["City"].isin(f.cities)
    if f.categories and "category" not in ignore:
        mask &= df["Main_Category"].isin(f.categories)
    if f.subcategories and "category" not in ignore:  # alt kategori de "kategori" filtresinin parçası
        mask &= df["Category_Standardized"].isin(f.subcategories)
    if f.segments and "segment" not in ignore:
        mask &= df["Segment"].isin(f.segments)
    return df.loc[mask]


def previous_period(f: Filters, data_start: dt.date) -> Filters | None:
    """Karşılaştırma dönemi: çeyrekte önceki çeyrek, özel aralıkta eşit uzunlukta önceki dönem."""
    if f.period == "Tüm yıl 2020":
        return None
    if f.is_quarter:
        names = list(PERIODS)
        i = names.index(f.period)
        if i <= 1:  # 1. çeyrekten önce veri yok
            return None
        s, e = PERIODS[names[i - 1]]
        return replace(f, period=names[i - 1], start=s, end=e)
    length = f.end - f.start + dt.timedelta(days=1)
    prev_end = f.start - dt.timedelta(days=1)
    prev_start = prev_end - length + dt.timedelta(days=1)
    if prev_start < data_start:
        return None
    return replace(f, period=CUSTOM_PERIOD, start=prev_start, end=prev_end)


def period_name(f: Filters) -> str:
    """Dönemin okunur adı: hazır dönemde adı, özel aralıkta tarihleri."""
    return f.period if f.period in PERIODS else f"{fmt_date(f.start)} – {fmt_date(f.end)}"


def comparison_label(f: Filters) -> str:
    return "önceki çeyreğe göre" if f.is_quarter else "önceki eşit döneme göre"


def describe(f: Filters) -> str:
    """Filtre durumunu tek satırda anlatır."""
    def part(values, all_label, unit):
        if not values:
            return all_label
        return ", ".join(values) if len(values) <= 2 else f"{len(values)} {unit}"
    return (f"{period_name(f)}; {part(f.cities, 'tüm iller', 'il')}; {part(f.categories, 'tüm ana kategoriler', 'ana kategori')}"
            f"{'; ' + part(f.subcategories, '', 'alt kategori') if f.subcategories else ''}; "
            f"{part(f.segments, 'tüm segmentler', 'segment')}")

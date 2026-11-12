"""Temizlenmiş verinin uygulamaya yüklenmesi."""

import json

import pandas as pd
import streamlit as st

from src.config import DATA_PATH, REPORT_PATH, SEGMENTS
from src.segments import segment_customers


@st.cache_resource(show_spinner="Veri yükleniyor...")
def load_data() -> tuple[pd.DataFrame, float]:
    """Temiz veriyi okur, müşteri segmentini ekler; tüm oturumlar aynı tabloyu paylaşır.

    cache_resource kullanıyoruz çünkü cache_data her çağrıda ~650 bin satırlık
    tablonun kopyasını üretir. Karşılığında bu tablo hiçbir yerde yerinde
    değiştirilmez; filtreleme her zaman yeni bir tablo döndürür.
    """
    df = pd.read_parquet(DATA_PATH)
    segments, silhouette = segment_customers(df)
    df["Segment"] = pd.Categorical(df["CustomerID"].map(segments), categories=SEGMENTS)
    return df, silhouette


@st.cache_data
def load_cleaning_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Kayıp riski modeli hazırlanıyor...")
def load_churn():
    """Churn modelini bir kez eğitir; skorlar ve doğrulama sonuçları tüm oturumlarda paylaşılır."""
    from src.churn import build
    df, _ = load_data()
    return build(df)


@st.cache_resource
def category_tree() -> dict:
    """Ana kategori → alt kategoriler (filtre seçenekleri için)."""
    from src.categories import MAIN_CATEGORIES
    df, _ = load_data()
    t = df.groupby("Main_Category", observed=True)["Category_Standardized"].unique()
    return {m: sorted(t[m].tolist()) for m in MAIN_CATEGORIES if m in t.index}


def _scope(df, cities: tuple, categories: tuple, segments: tuple, subcategories: tuple = ()):
    if cities:
        df = df[df["City"].isin(cities)]
    if categories:
        df = df[df["Main_Category"].isin(categories)]
    if segments:
        df = df[df["Segment"].isin(segments)]
    if subcategories:
        df = df[df["Category_Standardized"].isin(subcategories)]
    return df


@st.cache_data(show_spinner="Tahmin hesaplanıyor...")
def load_forecast(cities: tuple = (), categories: tuple = (), segments: tuple = (),
                  value: str = "Revenue", horizon: int = 8, cap: bool = True, subcategories: tuple = ()) -> dict:
    """Dönem filtresinden bağımsız: tahmin her zaman 2020'nin tüm haftalarıyla kurulur."""
    from src.forecast import run, weekly_series
    df, _ = load_data()
    return run(weekly_series(_scope(df, cities, categories, segments, subcategories), value), horizon, cap)


@st.cache_data(show_spinner="Kategori tahminleri hesaplanıyor...")
def load_category_forecasts(cities: tuple = (), categories: tuple = (), segments: tuple = (),
                            value: str = "Revenue", horizon: int = 8, cap: bool = True, n: int = 5,
                            subcategories: tuple = ()):
    """Kapsamdaki en büyük n kategori için ayrı ayrı tahmin özeti."""
    import pandas as pd
    from src.forecast import run, weekly_series
    df, _ = load_data()
    scope = _scope(df, cities, categories, segments, subcategories)
    rows = []
    for cat in scope.groupby("Category_Standardized", observed=True)["Revenue"].sum().nlargest(n).index:
        r = run(weekly_series(scope[scope["Category_Standardized"] == cat], value), horizon, cap)
        row = {"category": cat, "enough": r["enough_data"], "active_weeks": r["active_weeks"]}
        if r["enough_data"]:
            fc = r["forecast"]
            row.update(last8=r["last8_mean"], mean=fc["point"].mean(), lo=fc["lo"].mean(), hi=fc["hi"].mean(),
                       model=r["best"], mape=r["table"].loc[r["best"], "mape"], signal=r["signal"],
                       beats_naive=r["beats_naive"])
        rows.append(row)
    return pd.DataFrame(rows)


@st.cache_data
def load_category_audit():
    """data_prep.py'nin ürettiği kategori eşleme denetim tablosu."""
    import pandas as pd
    from src.config import REPORT_PATH
    return pd.read_csv(REPORT_PATH.parent / "category_mapping.csv")

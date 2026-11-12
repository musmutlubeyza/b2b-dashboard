"""Temizlenmiş verinin uygulamaya yüklenmesi."""

import json

import pandas as pd
import streamlit as st

from src.config import DATA_PATH, REPORT_PATH, SEGMENTS
from src.segments import segment_customers


# Kod değiştiğinde (yerelde dosyalar kopyalandığında ya da Streamlit Cloud yeni sürümü çektiğinde) bu modül
# yeniden yüklenir. Eski önbellekteki tablolar yeni kodla uyuşmayabilir (ör. segment adları değiştiğinde
# tablolar boş görünür); bu yüzden modül her yüklendiğinde tüm önbellek temizlenir.
st.cache_data.clear()
st.cache_resource.clear()


def _stamp() -> tuple:
    """Önbellek anahtarı: veri dosyasının değişme zamanı ve segment adları.
    data_prep yeniden çalıştırıldığında ya da segment adları değiştiğinde önbellek kendiliğinden yenilenir."""
    return DATA_PATH.stat().st_mtime, tuple(SEGMENTS)


@st.cache_resource(show_spinner="Veri yükleniyor...")
def _load_data(stamp: tuple) -> tuple[pd.DataFrame, float]:
    df = pd.read_parquet(DATA_PATH)
    segments, silhouette = segment_customers(df)
    df["Segment"] = pd.Categorical(df["CustomerID"].map(segments), categories=SEGMENTS)
    return df, silhouette


def load_data() -> tuple[pd.DataFrame, float]:
    """Temiz veriyi okur, müşteri segmentini ekler; tüm oturumlar aynı tabloyu paylaşır.

    cache_resource kullanıyoruz çünkü cache_data her çağrıda ~650 bin satırlık
    tablonun kopyasını üretir. Karşılığında bu tablo hiçbir yerde yerinde
    değiştirilmez; filtreleme her zaman yeni bir tablo döndürür.
    """
    return _load_data(_stamp())


@st.cache_data
def load_cleaning_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Kayıp riski modeli hazırlanıyor...")
def _load_churn(stamp: tuple):
    from src.churn import build
    df, _ = load_data()
    return build(df)


def load_churn():
    """Churn modelini bir kez eğitir; skorlar ve doğrulama sonuçları tüm oturumlarda paylaşılır."""
    return _load_churn(_stamp())


@st.cache_resource
def category_tree() -> dict:
    """Ana kategori → alt kategoriler (filtre seçenekleri için)."""
    from src.categories import MAIN_CATEGORIES
    df, _ = load_data()
    t = df.groupby("Main_Category", observed=True)["Category_Standardized"].unique()
    from src.formatting import tr_sort_key
    mains = sorted([m for m in MAIN_CATEGORIES if m in t.index and m != "Diğer"], key=tr_sort_key)
    mains += [m for m in ["Diğer"] if m in t.index]  # "Diğer" alfabeye katılmaz, en sonda
    return {m: sorted(t[m].tolist(), key=tr_sort_key) for m in mains}


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
                  value: str = "Revenue", horizon: int = 8, adjust: bool = True, subcategories: tuple = ()) -> dict:
    """Dönem filtresinden bağımsız: tahmin her zaman 2020'nin tüm haftalarıyla kurulur."""
    import pandas as pd
    from src.forecast import run, weekly_series
    df, _ = load_data()
    scope = _scope(df, cities, categories, segments, subcategories)
    r = run(weekly_series(scope, value), horizon, adjust)
    last = scope[scope["InvoiceWeek"] == pd.Timestamp("2020-12-28")]  # kısmi son hafta (28–31 Aralık)
    r["partial_last"] = (pd.Timestamp("2020-12-28"), float(last[value].sum()), int(last["InvoiceDate"].dt.date.nunique()))
    return r


@st.cache_data(show_spinner="Kategori tahminleri hesaplanıyor...")
def load_category_forecasts(cities: tuple = (), categories: tuple = (), segments: tuple = (),
                            value: str = "Revenue", horizon: int = 8, adjust: bool = True, n: int = 5,
                            subcategories: tuple = ()):
    """Kapsamdaki en büyük n kategori için ayrı ayrı tahmin özeti."""
    import pandas as pd
    from src.forecast import run, weekly_series
    df, _ = load_data()
    scope = _scope(df, cities, categories, segments, subcategories)
    rows = []
    for cat in scope.groupby("Category_Standardized", observed=True)["Revenue"].sum().nlargest(n).index:
        r = run(weekly_series(scope[scope["Category_Standardized"] == cat], value), horizon, adjust)
        row = {"category": cat, "enough": r["enough_data"], "active_weeks": r["active_weeks"]}
        if r["enough_data"]:
            fc = r["forecast"]
            row.update(last8=r["last8_mean"], mean=fc["point"].mean(), lo=fc["lo"].mean(), hi=fc["hi"].mean(),
                       model=r["best"], mape=r["table"].loc[r["best"], "mape"], signal=r["signal"],
                       beats_naive=r["beats_naive"], unit="TL" if value == "Revenue" else "adet")
        rows.append(row)
    return pd.DataFrame(rows)


@st.cache_data
def load_category_audit():
    """data_prep.py'nin ürettiği kategori eşleme denetim tablosu."""
    import pandas as pd
    from src.config import REPORT_PATH
    return pd.read_csv(REPORT_PATH.parent / "category_mapping.csv")


@st.cache_data
def load_review_records():
    """Hesaplamalardan ayrılan, kaynak sistemde kontrol edilecek kayıtlar (data_prep.py üretir)."""
    import pandas as pd
    from src.config import REPORT_PATH
    path = REPORT_PATH.parent / "review_records.csv"
    return pd.read_csv(path, dtype={"StockCode": str}) if path.exists() else pd.DataFrame()

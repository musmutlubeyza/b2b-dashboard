"""Müşteri segmentasyonu (k-ortalamalar).

Segmentler 2020 yıl sonu itibarıyla, müşterinin tüm yıldaki davranışından
belirlenir ve tüm sayfalarda sabit bir müşteri özelliği olarak kullanılır.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

N_SEGMENTS = 4
RANDOM_STATE = 42


def customer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Müşteri başına kümeleme değişkenleri."""
    end = df["InvoiceDate"].max()
    g = df.groupby("CustomerID")
    f = pd.DataFrame({
        "invoices": g["InvoiceNo"].nunique(),
        "revenue": g["Revenue"].sum(),
        "recency": (end - g["InvoiceDate"].max()).dt.days,
        "discount": 1 - g["Revenue"].sum() / g["ListValue"].sum(),
        "categories": g["Category_Standardized"].nunique(),
    })
    f["basket"] = f["revenue"] / f["invoices"]
    return f


def segment_customers(df: pd.DataFrame) -> tuple[pd.Series, float]:
    """Her müşteriye segment adı atar; segmentleri ve silhouette skorunu döndürür."""
    f = customer_features(df)
    # Çarpık dağılımlı değişkenler log ile yumuşatılır, sonra standartlaştırılır
    X = pd.DataFrame({
        "log_invoices": np.log1p(f["invoices"]),
        "log_revenue": np.log1p(f["revenue"]),
        "recency": f["recency"],
        "discount": f["discount"].clip(0, 0.8),
        "log_categories": np.log1p(f["categories"]),
        "log_basket": np.log1p(f["basket"]),
    })
    Xs = StandardScaler().fit_transform(X)
    labels = KMeans(N_SEGMENTS, n_init=10, random_state=RANDOM_STATE).fit_predict(Xs)
    score = float(silhouette_score(Xs, labels))

    # Küme numaraları rastgeledir; adları profilden kurallarla veriyoruz
    prof = f.assign(cl=labels).groupby("cl").agg(
        revenue=("revenue", "sum"), recency=("recency", "median"), basket=("basket", "median"))
    names = {}
    core = prof["revenue"].idxmax(); names[core] = "Çekirdek kitabevleri"
    rest = prof.drop(core)
    dormant = rest["recency"].idxmax(); names[dormant] = "Uykudaki müşteriler"
    rest = rest.drop(dormant)
    bulk = rest["basket"].idxmax(); names[bulk] = "Toplu alıcılar"
    names[rest.drop(bulk).index[0]] = "Düzenli küçük alıcılar"

    return pd.Series(labels, index=f.index).map(names).rename("Segment"), score

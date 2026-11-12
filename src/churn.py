"""Kayıp riski (churn) modeli.

Tanım: müşteri sonraki 92 günde hiç alım yapmazsa "kayıp" sayılır.
Model: lojistik regresyon (yorumlanabilir; random forest daha iyi sonuç vermedi).
Doğrulama: zamansal test — 30 Haziran verisiyle eğitilip 30 Eylül'de sınanır ve
yalnızca "son alımdan geçen gün" kuralıyla karşılaştırılır.
Skor: 30 Eylül'e kadarki veriyle eğitilen model yıl sonu (31 Aralık) verisine
uygulanır; yani Ocak–Mart 2021 için tahmin üretir. Dönem ve kategori
filtrelerinden bağımsızdır.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZON_DAYS = 92


def features(df: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Kesim tarihine kadarki davranıştan müşteri başına özellikler (geleceği görmez)."""
    obs = df[df["InvoiceDate"] <= cutoff]
    g = obs.groupby("CustomerID")
    X = pd.DataFrame({
        "recency": (cutoff - g["InvoiceDate"].max()).dt.days,
        "tenure": (cutoff - g["InvoiceDate"].min()).dt.days,
        "frequency": g["InvoiceNo"].nunique(),
        "log_revenue": np.log1p(g["Revenue"].sum()),
        "discount": 1 - g["Revenue"].sum() / g["ListValue"].sum(),
        "categories": g["Category_Standardized"].nunique(),
    })
    last90 = obs[obs["InvoiceDate"] > cutoff - pd.Timedelta(days=90)].groupby("CustomerID")["InvoiceNo"].nunique()
    X["invoices_last90"] = last90.reindex(X.index).fillna(0)
    days = obs.drop_duplicates("InvoiceNo").sort_values("InvoiceDate").groupby("CustomerID")["InvoiceDate"]
    X["mean_gap"] = days.apply(lambda s: s.diff().dt.days.mean()).reindex(X.index).fillna(X["tenure"])
    X["recency_vs_gap"] = X["recency"] / X["mean_gap"].replace(0, 1)
    return X


def labels(df: pd.DataFrame, X: pd.DataFrame, cutoff: pd.Timestamp) -> pd.Series:
    window = df[(df["InvoiceDate"] > cutoff) & (df["InvoiceDate"] <= cutoff + pd.Timedelta(days=HORIZON_DAYS))]
    return pd.Series((~X.index.isin(window["CustomerID"].unique())).astype(int), index=X.index)


def _top20_hit(y: pd.Series, score: np.ndarray) -> float:
    """En riskli %20'lik dilimde gerçekten kaybedilenlerin oranı."""
    k = int(len(y) * 0.2)
    return float(y.values[np.argsort(-score)[:k]].mean())


def build(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Modeli doğrular, eğitir ve yıl sonu itibarıyla tüm müşterileri skorlar."""
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    c1, c2, end = pd.Timestamp("2020-06-30"), pd.Timestamp("2020-09-30"), df["InvoiceDate"].max()

    X1, X2 = features(df, c1), features(df, c2)
    y1, y2 = labels(df, X1, c1), labels(df, X2, c2)
    p2 = model.fit(X1, y1).predict_proba(X2)[:, 1]
    report = {"auc_model": roc_auc_score(y2, p2), "auc_rule": roc_auc_score(y2, X2["recency"]),
              "hit_model": _top20_hit(y2, p2), "hit_rule": _top20_hit(y2, X2["recency"].values),
              "base_rate": float(y2.mean()), "n_test": len(y2)}

    model.fit(X2, y2)                      # son etiketli kesimle yeniden eğit
    X_end = features(df, end)
    scores = pd.DataFrame({"probability": model.predict_proba(X_end)[:, 1]}, index=X_end.index)
    g = df.groupby("CustomerID")
    scores["revenue"] = g["Revenue"].sum()
    scores["last_purchase"] = g["InvoiceDate"].max()
    scores["city"] = g["City"].first()
    scores["risk_revenue"] = scores["probability"] * scores["revenue"]
    return scores.sort_values("risk_revenue", ascending=False), report

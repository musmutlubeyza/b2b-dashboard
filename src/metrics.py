"""KPI'lar ve özet tablolar. Bu modül yalnızca hesap yapar (Streamlit içermez);
aynı fonksiyonlar sayfalarda, aksiyon motorunda ve sohbette kullanılır."""

import datetime as dt

import pandas as pd

from src.config import SEGMENTS


def kpis(df: pd.DataFrame) -> dict:
    revenue = float(df["Revenue"].sum())
    invoices = int(df["InvoiceNo"].nunique())
    return {"revenue": revenue, "invoices": invoices,
            "avg_invoice": revenue / invoices if invoices else 0.0,
            "customers": int(df["CustomerID"].nunique())}


def weekly_revenue(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.Series:
    """Dönemdeki haftalık ciro; satış olmayan haftalar 0 (boşluk görünür kalsın diye)."""
    weeks = pd.date_range(pd.Timestamp(start) - pd.Timedelta(days=start.weekday()), pd.Timestamp(end), freq="W-MON")
    return df.groupby("InvoiceWeek")["Revenue"].sum().reindex(weeks, fill_value=0.0)


def quarter_revenue(df: pd.DataFrame) -> pd.Series:
    return df.groupby(df["InvoiceDate"].dt.quarter)["Revenue"].sum().reindex([1, 2, 3, 4], fill_value=0.0)


def segment_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Segment başına müşteri sayısı, müşteri payı ve ciro payı (sabit segment sırasıyla)."""
    g = df.groupby("Segment", observed=False).agg(customers=("CustomerID", "nunique"), revenue=("Revenue", "sum"))
    g = g.reindex(SEGMENTS).fillna(0)
    g["customer_share"] = g["customers"] / max(g["customers"].sum(), 1)
    g["revenue_share"] = g["revenue"] / max(g["revenue"].sum(), 1)
    return g


def category_movers(cur: pd.DataFrame, prev: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Önceki döneme göre cirosu en çok artan ve azalan n kategori."""
    t = pd.DataFrame({"prev": prev.groupby("Category_Standardized", observed=True)["Revenue"].sum(),
                      "cur": cur.groupby("Category_Standardized", observed=True)["Revenue"].sum()}).fillna(0)
    t["diff"] = t["cur"] - t["prev"]
    t["pct"] = t["diff"] / t["prev"].where(t["prev"] > 0)
    up = t[t["diff"] > 0].nlargest(n, "diff")
    down = t[t["diff"] < 0].nsmallest(n, "diff")
    return pd.concat([up, down])


def lost_customers(cur: pd.DataFrame, prev: pd.DataFrame) -> pd.DataFrame:
    """Önceki dönemde alım yapıp bu dönemde yapmayan müşteriler ve önceki dönem cirosu."""
    lost = set(prev["CustomerID"]) - set(cur["CustomerID"])
    p = prev[prev["CustomerID"].isin(lost)]
    return (p.groupby("CustomerID").agg(revenue=("Revenue", "sum"), city=("City", "first"))
            .sort_values("revenue", ascending=False))


def customer_flow(scope: pd.DataFrame, cur: pd.DataFrame, prev: pd.DataFrame, start) -> dict:
    """Önceki dönemden seçili döneme müşteri hareketi.
    scope: dönem dışındaki filtreler uygulanmış tüm veri (müşterinin daha önce alım yapıp yapmadığı için)."""
    c, p = set(cur["CustomerID"]), set(prev["CustomerID"])
    before = set(scope.loc[scope["InvoiceDate"] < pd.Timestamp(start), "CustomerID"])
    return {"prev": len(p), "lost": len(p - c), "stay": len(p & c),
            "back": len((c - p) & before), "new": len(c - before), "cur": len(c)}


def city_table(cur: pd.DataFrame, prev: pd.DataFrame | None, n: int = 8) -> pd.DataFrame:
    t = cur.groupby("City", observed=True).agg(customers=("CustomerID", "nunique"), revenue=("Revenue", "sum"))
    t["share"] = t["revenue"] / t["revenue"].sum()
    t["per_customer"] = t["revenue"] / t["customers"]
    if prev is not None and not prev.empty:
        pr = prev.groupby("City", observed=True)["Revenue"].sum()
        t["change"] = t["revenue"] / pr.reindex(t.index) - 1
    return t.sort_values("revenue", ascending=False).head(n)


# --- Pazarlama ---


def segment_profiles(cur: pd.DataFrame, end) -> pd.DataFrame:
    """Seçili dönemde her segmentin ortanca davranışı (sütunlar segment)."""
    kids = cur["Main_Category"].eq("Çocuk ve Gençlik")
    c = cur.groupby("CustomerID").agg(segment=("Segment", "first"), revenue=("Revenue", "sum"),
                                      list_value=("ListValue", "sum"), invoices=("InvoiceNo", "nunique"),
                                      categories=("Category_Standardized", "nunique"), last=("InvoiceDate", "max"))
    c["kids"] = cur[kids].groupby("CustomerID")["Revenue"].sum().reindex(c.index).fillna(0) / c["revenue"]
    c["basket"] = c["revenue"] / c["invoices"]
    c["discount"] = 1 - c["revenue"] / c["list_value"]
    c["recency"] = (pd.Timestamp(end) - c["last"]).dt.days
    p = c.groupby("segment", observed=False).agg(customers=("revenue", "size"), revenue=("revenue", "sum"),
                                                 invoices=("invoices", "median"), recency=("recency", "median"),
                                                 categories=("categories", "median"), basket=("basket", "median"),
                                                 kids=("kids", "median"), discount=("discount", "median"))
    p["share"] = p["revenue"] / p["revenue"].sum()
    return p.reindex(SEGMENTS).T


def penetration(cur: pd.DataFrame, n: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    """En büyük n kategori için segment başına alım oranı ve kategoriyi almayan müşteri sayısı."""
    top = cur.groupby("Category_Standardized", observed=True)["Revenue"].sum().nlargest(n).index
    seg = cur.groupby("CustomerID")["Segment"].first()
    bought = (cur[cur["Category_Standardized"].isin(top)].groupby(["CustomerID", "Category_Standardized"], observed=True).size()
              .unstack(fill_value=0).reindex(index=seg.index, columns=top, fill_value=0) > 0)
    rate = bought.groupby(seg, observed=False).mean().reindex(SEGMENTS)
    missing = (~bought).groupby(seg, observed=False).sum().reindex(SEGMENTS)
    return rate, missing


def cross_sell(rate: pd.DataFrame, missing: pd.DataFrame, core: str = SEGMENTS[0], n: int = 5) -> pd.DataFrame:
    """Kural: segmentteki alım oranı çekirdek segmentin yarısından az olan kategoriler.
    Uykudaki müşteriler hariç: onlar için öncelik çapraz satış değil, yeniden kazanmaktır."""
    rows = []
    for s in rate.index:
        if s in (core, SEGMENTS[3]):
            continue
        for cat in rate.columns:
            if pd.notna(rate.loc[s, cat]) and rate.loc[s, cat] < rate.loc[core, cat] / 2:
                rows.append({"segment": s, "category": cat, "missing": int(missing.loc[s, cat]),
                             "rate": rate.loc[s, cat], "core_rate": rate.loc[core, cat]})
    return pd.DataFrame(rows).sort_values("missing", ascending=False).head(n) if rows else pd.DataFrame()


def customer_discounts(cur: pd.DataFrame) -> pd.DataFrame:
    c = cur.groupby("CustomerID").agg(revenue=("Revenue", "sum"), list_value=("ListValue", "sum"))
    c["discount"] = 1 - c["revenue"] / c["list_value"]
    return c


# --- Tedarik ---
def abc_xyz(df: pd.DataFrame) -> pd.DataFrame:
    """SKU başına ABC (ciro payı %80/%95) ve XYZ (aylık adet değişkenlik katsayısı 0,5/1,0)."""
    sku = df.groupby("StockCode")["Revenue"].sum().sort_values(ascending=False).to_frame("revenue")
    cum = sku["revenue"].cumsum() / sku["revenue"].sum()
    sku["abc"] = pd.cut(cum, [0, 0.8, 0.95, 1.0001], labels=["A", "B", "C"], include_lowest=True).astype(str)
    monthly = df.groupby(["StockCode", "InvoiceMonth"])["Quantity"].sum().unstack(fill_value=0)
    cv = (monthly.std(axis=1, ddof=0) / monthly.mean(axis=1)).reindex(sku.index)
    sku["xyz"] = pd.cut(cv, [-1, 0.5, 1.0, float("inf")], labels=["X", "Y", "Z"], right=False).astype(str)
    return sku


def weekday_share(cur: pd.DataFrame) -> pd.Series:
    q = cur.groupby("Weekday")["Quantity"].sum().reindex(range(7), fill_value=0)
    return q / q.sum() if q.sum() else q


def top_titles(cur: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    return (cur.groupby("Description").agg(quantity=("Quantity", "sum"), customers=("CustomerID", "nunique"),
                                           category=("Category_Standardized", "first"))
            .sort_values("quantity", ascending=False).head(n))

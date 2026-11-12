"""RFM: son alım (R), sıklık (F) ve tutar (M) için 1–5 arası dilim puanı.
Segmentler R ve F puanlarından türetilir. Hesap, dönem sonuna kadarki tüm geçmişle yapılır."""

import pandas as pd

ORDER = ["Şampiyonlar", "Sadık", "Potansiyel sadık", "Yeni / tek seferlik", "İlgi bekleyen", "Risk altında", "Kayıp"]
ACTIONS = {"Şampiyonlar": "Öncelikli sevkiyat, yeni çıkanları önce sun",
           "Sadık": "Sipariş sıklığını koru, çeşit genişlet",
           "Potansiyel sadık": "Düzenli sipariş için hatırlatma",
           "Yeni / tek seferlik": "İkinci siparişi teşvik et",
           "İlgi bekleyen": "Temsilci araması planla",
           "Risk altında": "Geri kazanım görüşmesi",
           "Kayıp": "Düşük maliyetli hatırlatma"}


def _score(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Sıralamaya göre 5 eşit dilim (eşit değerlerde dilim sınırı kaymasın diye rank)."""
    return pd.qcut(s.rank(method="first", ascending=ascending), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def _segment(r: int, f: int) -> str:
    if r >= 4 and f >= 4: return "Şampiyonlar"
    if r >= 3 and f >= 4: return "Sadık"
    if r >= 4 and f >= 2: return "Potansiyel sadık"
    if r >= 4: return "Yeni / tek seferlik"
    if r == 3: return "İlgi bekleyen"
    if f >= 3: return "Risk altında"
    return "Kayıp"


def rfm_table(df: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Müşteri başına R, F, M puanları ve RFM segmenti."""
    g = df.groupby("CustomerID")
    t = pd.DataFrame({"recency": (end - g["InvoiceDate"].max()).dt.days,
                      "frequency": g["InvoiceNo"].nunique(), "monetary": g["Revenue"].sum()})
    if len(t) < 5:
        return t.assign(rfm="—")
    t["R"] = _score(t["recency"], ascending=False)  # yakın tarih = yüksek puan
    t["F"], t["M"] = _score(t["frequency"]), _score(t["monetary"])
    t["rfm"] = [_segment(r, f) for r, f in zip(t["R"], t["F"])]
    return t


def rfm_summary(t: pd.DataFrame) -> pd.DataFrame:
    s = t.groupby("rfm").agg(customers=("monetary", "size"), revenue=("monetary", "sum"),
                             recency=("recency", "median"), frequency=("frequency", "median"))
    s["share"] = s["revenue"] / s["revenue"].sum()
    return s.reindex([o for o in ORDER if o in s.index])

"""RFM: son alım (R), sıklık (F) ve tutar (M) için 1–5 arası dilim puanı.
Segmentler R puanı ile FM puanından (F ve M'nin ortalaması, yarımlar yukarı yuvarlanır) türetilir;
böylece tutarı yüksek ama sıklığı düşen müşteriler "Kayıp" yerine "Risk Altında" görünür.
Hesap, dönem sonuna kadarki tüm geçmişle yapılır."""

import pandas as pd

ORDER = ["Şampiyonlar", "Sadık", "Potansiyel Sadık", "Yeni / Tek Seferlik", "İlgi Bekleyen", "Risk Altında", "Kayıp"]
ACTIONS = {"Şampiyonlar": "Öncelikli sevkiyat, yeni çıkanları önce sun",
           "Sadık": "Sipariş sıklığını koru, çeşit genişlet",
           "Potansiyel Sadık": "Düzenli sipariş için hatırlatma",
           "Yeni / Tek Seferlik": "İkinci siparişi teşvik et",
           "İlgi Bekleyen": "Temsilci araması planla",
           "Risk Altında": "Geri kazanım görüşmesi",
           "Kayıp": "Düşük maliyetli hatırlatma"}


def _score(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Sıralamaya göre 5 eşit dilim (eşit değerlerde dilim sınırı kaymasın diye rank)."""
    return pd.qcut(s.rank(method="first", ascending=ascending), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def _segment(r: int, fm: int) -> str:
    """R ve FM puanından segment (FM: sıklık ve tutar puanlarının ortalaması)."""
    if r >= 4 and fm >= 4: return "Şampiyonlar"
    if r >= 3 and fm >= 4: return "Sadık"
    if r >= 4 and fm >= 2: return "Potansiyel Sadık"
    if r >= 4: return "Yeni / Tek Seferlik"
    if r == 3: return "İlgi Bekleyen"
    if fm >= 3: return "Risk Altında"
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
    t["FM"] = ((t["F"] + t["M"]) / 2 + 0.5).astype(int)  # yarımlar yukarı: 3,5 -> 4
    t["rfm"] = [_segment(r, fm) for r, fm in zip(t["R"], t["FM"])]
    return t


def rfm_summary(t: pd.DataFrame) -> pd.DataFrame:
    s = t.groupby("rfm").agg(customers=("monetary", "size"), revenue=("monetary", "sum"),
                             recency=("recency", "median"), frequency=("frequency", "median"))
    s["share"] = s["revenue"] / s["revenue"].sum()
    return s.reindex([o for o in ORDER if o in s.index])

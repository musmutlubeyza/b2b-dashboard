"""Aksiyon motoru: her öneri açık bir kurala ve veriden gelen bir kanıta dayanır.

Kurallar Veri Notları sayfasında listelenir. Sohbet de yalnızca bu önerileri
kullanır; böylece sayfadaki ve sohbetteki öneriler hiçbir zaman çelişmez.
"""

from dataclasses import dataclass

import pandas as pd

from src.config import INACTIVE_DAYS, PAGE_FORECAST, PAGE_MARKETING, PAGE_SALES, PAGE_SUPPLY, WEEKDAYS_TR
from src.filters import Filters, period_name
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.metrics import lost_customers


@dataclass
class Action:
    dept: str            # Satış, Pazarlama, Tedarik, Yönetim, Veri
    title: str
    evidence: str
    page: str            # ayrıntı sayfasının dosya yolu
    link: str            # bağlantı metni
    forecast: bool = False
    impact: float = 0.0  # sıralama için (TL)


def winback(cur: pd.DataFrame, prev: pd.DataFrame, prev_f: Filters) -> Action | None:
    """Kural: önceki dönemde alıp seçili dönemde almayan müşteriler."""
    lost = lost_customers(cur, prev)
    if lost.empty:
        return None
    rev = float(lost["revenue"].sum())
    return Action("Satış", f"Kaybedilen {fmt_number(len(lost))} müşteri için geri kazanım başlat",
                  f"{period_name(prev_f)} cirosu {fmt_tl(rev)}; bu dönemde alım yok.", PAGE_SALES, "Kayıp riski", impact=rev)


def key_account(cur: pd.DataFrame, prev: pd.DataFrame, f: Filters, prev_f: Filters) -> Action | None:
    """Kural: önceki dönem cirosu en yüksek kaybedilen müşteri, 90 günden uzun süredir alım yapmıyorsa."""
    lost = lost_customers(cur, prev)
    if lost.empty:
        return None
    cid = lost.index[0]
    last = prev.loc[prev["CustomerID"] == cid, "InvoiceDate"].max()
    if (pd.Timestamp(f.end) - last).days <= INACTIVE_DAYS:
        return None
    return Action("Satış", f"{cid} kodlu müşteriyle görüş ({lost.iloc[0]['city']})",
                  f"{period_name(prev_f)} cirosu {fmt_tl(lost.iloc[0]['revenue'])}; {last:%d.%m.%Y} tarihinden beri alım yok.",
                  PAGE_SALES, "İller", impact=float(lost.iloc[0]["revenue"]))


def summary_actions(cur, prev, f, prev_f) -> list[Action]:
    """Yönetici Özeti'nde gösterilen öneriler (tahmine dayalı öneri Tahmin bölümünde eklenecek)."""
    if prev is None:
        return []
    found = [winback(cur, prev, prev_f), key_account(cur, prev, f, prev_f)]
    return [a for a in found if a is not None]


def risk_assignment(scores: pd.DataFrame, n: int = 20) -> Action | None:
    """Kural (tahmine dayalı): riskteki cirosu en yüksek n müşteriyi temsilcilere ata."""
    top = scores.head(n)
    if top.empty:
        return None
    first = top.iloc[0]
    return Action("Satış", f"Riskteki cirosu en yüksek {fmt_number(len(top))} müşteriyi temsilcilere ata",
                  f"Toplam {fmt_tl(top['risk_revenue'].sum())}; listenin başında {top.index[0]} "
                  f"(kayıp olasılığı {fmt_pct(first['probability'], 0)}).", PAGE_SALES, "Kayıp riski",
                  forecast=True, impact=float(top["risk_revenue"].sum()))


def second_order(new_customers: int) -> Action | None:
    """Kural: ilk alımını seçili dönemde yapan müşteriler."""
    if new_customers <= 0:
        return None
    return Action("Satış", f"{fmt_number(new_customers)} yeni müşteriye ikinci sipariş hatırlatması gönder",
                  "İlk alımlarını bu dönemde yaptılar.", PAGE_SALES, "Müşteri hareketi")


def cross_sell_campaign(targets: pd.DataFrame) -> Action | None:
    """Kural: segmentte kategori alım oranı çekirdek segmentin yarısından az."""
    if targets.empty:
        return None
    t = targets.iloc[0]
    return Action("Pazarlama", f"{t['segment']} segmentine {t['category']} kampanyası",
                  f"{fmt_number(t['missing'])} müşteri almadı; alım oranı {fmt_pct(t['rate'], 0)}, "
                  f"çekirdek kitabevlerinde {fmt_pct(t['core_rate'], 0)}.", PAGE_MARKETING, "Çapraz satış",
                  impact=float(t["missing"]))


def discount_review(discounts: pd.Series, low: float = 0.35, high: float = 0.45) -> Action | None:
    """Kural: ağırlıklı iskontosu %35–45 bandı dışında kalan müşteriler."""
    out = int(((discounts <= low) | (discounts > high)).sum())  # grafikteki dilimlerle aynı sınırlar
    if out == 0:
        return None
    return Action("Pazarlama", "İskonto koşullarını gözden geçir",
                  f"{fmt_number(out)} müşteri %35–45 bandının dışında.", PAGE_MARKETING, "İskonto")


def safety_stock(cells: pd.DataFrame) -> Action | None:
    """Kural: ABC-XYZ matrisinde AZ hücresindeki ürünler."""
    az = cells[(cells["abc"] == "A") & (cells["xyz"] == "Z")]
    if az.empty:
        return None
    share = az["revenue"].sum() / cells["revenue"].sum()
    return Action("Tedarik", "AZ ürünlerinde emniyet stokunu gözden geçir",
                  f"{fmt_number(len(az))} ürün, cironun {fmt_pct(share)} kadarı; aylık talebi düzensiz.",
                  PAGE_SUPPLY, "ABC-XYZ")


def capacity(shares: pd.Series, factor: float = 1.5) -> Action | None:
    """Kural: bir günün adet payı, salı–cuma ortalamasının 1,5 katını aşıyor."""
    base = shares.iloc[1:5].mean()
    day = int(shares.idxmax())
    if not base or shares[day] <= factor * base:
        return None
    return Action("Tedarik", f"{WEEKDAYS_TR[day]} depo kapasitesini artır",
                  f"Satılan adetin {fmt_pct(shares[day])} kadarı {WEEKDAYS_TR[day].lower()} günü; "
                  f"diğer iş günleri ortalaması {fmt_pct(base)}.", PAGE_SUPPLY, "İş yükü")


# --- Tahmine dayalı kurallar (yalnızca model naive referansını geçerse) ---
def horizon_label(fc: pd.DataFrame) -> str:
    from src.formatting import fmt_date
    return f"{fmt_date(fc.index[0])} – {fmt_date(fc.index[-1] + pd.Timedelta(days=6))}"


def plan_with_forecast(r: dict) -> Action | None:
    """Kural: toplam ciro tahmini ve %80 aralığı; sipariş planına girdi."""
    if not r.get("enough_data") or not r.get("beats_naive"):
        return None
    return Action("Tedarik", f"{len(r['forecast'])} haftalık siparişleri tahmine göre planla",
                  f"Tahmini ciro {fmt_tl(r['total'])}, %80 aralığı {fmt_tl(r['total_lo'])} – {fmt_tl(r['total_hi'])}.",
                  PAGE_FORECAST, "Tahmin", forecast=True)


def targets_from_forecast(r: dict) -> Action | None:
    """Kural: hedefler tahmin aralığına göre belirlenir."""
    if not r.get("enough_data") or not r.get("beats_naive"):
        return None
    return Action("Yönetim", "Ciro hedeflerini tahmin aralığına göre belirle",
                  f"{horizon_label(r['forecast'])}: {fmt_tl(r['total'])} "
                  f"(%80 aralığı {fmt_tl(r['total_lo'])} – {fmt_tl(r['total_hi'])}).", PAGE_FORECAST, "Haftalık tahmin",
                  forecast=True)


def category_signals(cats: pd.DataFrame, dept: str) -> list[Action]:
    """Kural: kategori tahmininin alt sınırı son 8 haftanın ortalamasının üzerinde (artış) ya da üst sınırı altında (düşüş)."""
    out = []
    if cats.empty or "signal" not in cats:
        return out
    for r in cats[cats["enough"] & cats["beats_naive"].fillna(False).astype(bool)].itertuples():
        if r.signal == "artış":
            title = (f"{r.category} siparişini öne çek" if dept == "Tedarik"
                     else f"Kampanya için {r.category} kategorisini değerlendir")
        elif r.signal == "düşüş" and dept == "Tedarik":
            title = f"{r.category} alımını azalt"
        else:
            continue
        out.append(Action(dept, title, f"Haftalık tahmin aralığı {fmt_tl(r.lo)} – {fmt_tl(r.hi)}; "
                          f"son 8 hafta ortalaması {fmt_tl(r.last8)}.", PAGE_FORECAST, "Kategori tahminleri", forecast=True))
    return out


def monitoring() -> Action:
    return Action("Veri", "Tahmini her hafta gerçekleşenle karşılaştır",
                  "Gerçekleşen %80 aralığın dışına çıkarsa model yeniden kurulmalı.", PAGE_FORECAST, "Model karşılaştırması")

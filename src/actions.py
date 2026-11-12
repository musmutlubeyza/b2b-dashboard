"""Aksiyon motoru: her öneri açık bir kurala ve veriden gelen bir kanıta dayanır.

Kurallar Veri Notları sayfasında listelenir. Her öneri, ayrıntısının bulunduğu sayfayı ve
sekmeyi taşır; bağlantı doğrudan o sekmeyi açar.
"""

from dataclasses import dataclass

import pandas as pd

from src.config import INACTIVE_DAYS, PAGE_FORECAST, PAGE_MARKETING, PAGE_SALES, PAGE_SUPPLY, WEEKDAYS_TR
from src.filters import Filters, period_name
from src.formatting import fmt_date, fmt_number, fmt_pct, fmt_tl, tr_lower
from src.metrics import inactive_customers


@dataclass
class Action:
    dept: str            # Satış, Pazarlama, Tedarik, Yönetim, Veri
    title: str
    evidence: str
    page: str            # ayrıntı sayfasının dosya yolu
    link: str            # bağlantı metni
    forecast: bool = False
    impact: float = 0.0  # sıralama için (TL)
    tab: str | None = None  # bağlantının açacağı sekme


def reactivation(cur: pd.DataFrame, prev: pd.DataFrame, prev_f: Filters) -> Action | None:
    """Kural: önceki dönemde alıp seçili dönemde almayan (hareketsiz) müşteriler."""
    inactive = inactive_customers(cur, prev)
    if inactive.empty:
        return None
    rev = float(inactive["revenue"].sum())
    return Action("Satış", f"Hareketsiz {fmt_number(len(inactive))} müşteriyle yeniden temas kur",
                  f"{period_name(prev_f)} cirosu {fmt_tl(rev)}; bu dönemde alım yok.", PAGE_SALES, "Müşteri hareketi",
                  impact=rev, tab="Müşteri Hareketi")


def key_account(cur: pd.DataFrame, prev: pd.DataFrame, f: Filters, prev_f: Filters) -> Action | None:
    """Kural: önceki dönem cirosu en yüksek hareketsiz müşteri, 90 günden uzun süredir alım yapmıyorsa."""
    inactive = inactive_customers(cur, prev)
    if inactive.empty:
        return None
    cid = inactive.index[0]
    last = prev.loc[prev["CustomerID"] == cid, "InvoiceDate"].max()
    if (pd.Timestamp(f.end) - last).days <= INACTIVE_DAYS:
        return None
    return Action("Satış", f"{cid} kodlu müşteriyle görüş ({inactive.iloc[0]['city']})",
                  f"{period_name(prev_f)} cirosu {fmt_tl(inactive.iloc[0]['revenue'])}; {last:%d.%m.%Y} tarihinden beri alım yok.",
                  PAGE_SALES, "Kayıp riski", impact=float(inactive.iloc[0]["revenue"]), tab="Kayıp Riski")


def summary_actions(cur, prev, f, prev_f) -> list[Action]:
    """Yönetici Özeti'nde gösterilen veriye dayalı öneriler."""
    if prev is None:
        return []
    found = [reactivation(cur, prev, prev_f), key_account(cur, prev, f, prev_f)]
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
                  forecast=True, impact=float(top["risk_revenue"].sum()), tab="Kayıp Riski")


def second_order(new_customers: int) -> Action | None:
    """Kural: ilk alımını seçili dönemde yapan müşteriler."""
    if new_customers <= 0:
        return None
    return Action("Satış", f"{fmt_number(new_customers)} yeni müşteriye ikinci sipariş hatırlatması gönder",
                  "İlk alımlarını bu dönemde yaptılar.", PAGE_SALES, "Müşteri hareketi", tab="Müşteri Hareketi")


def cross_sell_campaign(targets: pd.DataFrame) -> Action | None:
    """Kural: segmentte kategori alım oranı çekirdek segmentin yarısından az."""
    if targets.empty:
        return None
    t = targets.iloc[0]
    return Action("Pazarlama", f"{t['segment']} segmentine {t['category']} kampanyası",
                  f"{fmt_number(t['missing'])} müşteri almadı; alım oranı {fmt_pct(t['rate'], 0)}, "
                  f"Çekirdek Kitabevleri'nde {fmt_pct(t['core_rate'], 0)}.", PAGE_MARKETING, "Çapraz satış",
                  impact=float(t["missing"]), tab="Kategori ve Çapraz Satış")


def discount_review(discounts: pd.Series, low: float = 0.35, high: float = 0.45) -> Action | None:
    """Kural: ağırlıklı iskontosu %35–45 bandı dışında kalan müşteriler."""
    out = int(((discounts <= low) | (discounts > high)).sum())  # grafikteki dilimlerle aynı sınırlar
    if out == 0:
        return None
    return Action("Pazarlama", "İskonto koşullarını gözden geçir",
                  f"{fmt_number(out)} müşteri %35–45 bandının dışında.", PAGE_MARKETING, "İskonto", tab="İskonto")


def close_monitoring(cells: pd.DataFrame) -> Action | None:
    """Kural: ABC-XYZ matrisinin AZ hücresi (ciroya katkısı yüksek, talebi düzensiz ürünler)."""
    az = cells[(cells["abc"] == "A") & (cells["xyz"] == "Z")]
    if az.empty:
        return None
    share = az["revenue"].sum() / cells["revenue"].sum()
    return Action("Tedarik", "AZ ürünlerini yakın takibe al",
                  f"{fmt_number(len(az))} ürün, cironun {fmt_pct(share)} kadarı; aylık talebi düzensiz.",
                  PAGE_SUPPLY, "ABC-XYZ", tab="ABC-XYZ Önceliklendirme")


def capacity(shares: pd.Series, factor: float = 1.5) -> Action | None:
    """Kural: bir günün adet payı, salı–cuma ortalamasının 1,5 katını aşıyor."""
    base = shares.iloc[1:5].mean()
    day = int(shares.idxmax())
    if not base or shares[day] <= factor * base:
        return None
    return Action("Tedarik", f"{WEEKDAYS_TR[day]} depo kapasitesini artır",
                  f"Satılan adetin {fmt_pct(shares[day])} kadarı {tr_lower(WEEKDAYS_TR[day])} günü; "
                  f"diğer iş günleri ortalaması {fmt_pct(base)}.", PAGE_SUPPLY, "İş yükü", tab="İş Yükü")


def volume_plan(units: dict, shares: pd.Series) -> Action | None:
    """Kural (tahmine dayalı): 8 haftalık adet tahmini ve son 13 haftanın gün dağılımıyla sevkiyat kapasitesi planı.
    Seçilen model naive referansını geçemezse plan referans tahminle (son haftaların seviyesi) yapılır ve
    bu, kanıt satırında açıkça yazılır. Ufuk ve aralık kartta verilir."""
    if not units or not units.get("enough_data") or shares.empty:
        return None
    fc = units["forecast"]
    weekly = fc["point"].mean()
    day = int(shares.idxmax())
    method = (f"Yöntem: {tr_lower(units['best'])}" if units.get("beats_naive")
              else "Yöntem: naive (modeller referansı geçemedi)")
    day_month = lambda d: fmt_date(d).rsplit(" ", 1)[0]  # "4 Ocak"
    span = f"{day_month(fc.index[0])} – {day_month(fc.index[-1] + pd.Timedelta(days=6))}"
    return Action("Tedarik", f"{span} sevkiyat kapasitesini haftada {fmt_number(weekly)} adete göre planla",
                  f"8 haftada {fmt_number(units['total'])} adet (%80: {fmt_number(units['total_lo'])} – "
                  f"{fmt_number(units['total_hi'])}); {tr_lower(WEEKDAYS_TR[day])} başına ~{fmt_number(weekly * shares[day])} adet. "
                  f"{method}.",
                  PAGE_SUPPLY, "Adet tahmini", forecast=True, tab="Adet Tahmini")


# --- Tahmine dayalı kurallar (yalnızca seçilen model naive referansını geçerse) ---
def horizon_label(fc: pd.DataFrame) -> str:
    return f"{fmt_date(fc.index[0])} – {fmt_date(fc.index[-1] + pd.Timedelta(days=6))}"


def plan_with_forecast(r: dict) -> Action | None:
    """Kural: toplam ciro tahmini ve %80 aralığı; sipariş planına girdi."""
    if not r.get("enough_data") or not r.get("beats_naive"):
        return None
    return Action("Tedarik", f"{len(r['forecast'])} haftalık siparişleri tahmine göre planla",
                  f"Tahmini ciro {fmt_tl(r['total'])}, %80 aralığı {fmt_tl(r['total_lo'])} – {fmt_tl(r['total_hi'])}.",
                  PAGE_FORECAST, "Tahmin", forecast=True, tab="Haftalık Tahmin")


def targets_from_forecast(r: dict) -> Action | None:
    """Kural: hedefler tahmin aralığına göre belirlenir."""
    if not r.get("enough_data") or not r.get("beats_naive"):
        return None
    return Action("Yönetim", "Ciro hedeflerini tahmin aralığına göre belirle",
                  f"{horizon_label(r['forecast'])}: {fmt_tl(r['total'])} "
                  f"(%80 aralığı {fmt_tl(r['total_lo'])} – {fmt_tl(r['total_hi'])}).", PAGE_FORECAST, "Haftalık tahmin",
                  forecast=True, tab="Haftalık Tahmin")


def category_signals(cats: pd.DataFrame, dept: str) -> list[Action]:
    """Kural: kategori tahmininin alt sınırı son 8 haftanın ortalamasının üzerinde (artış) ya da üst sınırı altında (düşüş).
    Tedarik için adet, pazarlama için ciro serisi kullanılır."""
    out = []
    if cats.empty or "signal" not in cats:
        return out
    for r in cats[cats["enough"] & cats["beats_naive"].fillna(False).astype(bool)].itertuples():
        fmt = fmt_tl if getattr(r, "unit", "TL") == "TL" else (lambda v: f"{fmt_number(v)} adet")
        if r.signal == "artış":
            title = (f"{r.category} siparişini öne çek" if dept == "Tedarik"
                     else f"Kampanya için {r.category} kategorisini değerlendir")
        elif r.signal == "düşüş" and dept == "Tedarik":
            title = f"{r.category} alımını azalt"
        else:
            continue
        out.append(Action(dept, title, f"Haftalık tahmin aralığı {fmt(r.lo)} – {fmt(r.hi)}; "
                          f"son 8 hafta ortalaması {fmt(r.last8)}.", PAGE_FORECAST, "Kategori tahminleri", forecast=True,
                          tab="Kategori Tahminleri"))
    return out


def monitoring() -> Action:
    return Action("Veri", "Tahmini her hafta gerçekleşenle karşılaştır",
                  "Gerçekleşen %80 aralığın dışına çıkarsa model yeniden kurulmalı.", PAGE_FORECAST, "Model karşılaştırması",
                  tab="Model Karşılaştırması")

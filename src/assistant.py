"""Yönetici Özeti'ndeki "Asistana sor" için bilgi katmanı.

Asistan sayfadaki filtrelere bağlı değildir; kapsamı soru belirler. Soruda dönem yoksa sayfadaki
dönem kullanılır, diğer sayfa filtreleri (il, kategori, segment) asistanı etkilemez.

Akış (serbest soru):
1. Çözümleme: dil modeli sorudan kapsamı (dönem, il, kategori, segment, kırılım) ve konuyu JSON olarak çıkarır.
2. Doğrulama ve hesaplama: değerler geçerli listelerle eşlenir (tanınmayan değer uydurulmaz), kapsam
   paneldeki analiz fonksiyonlarıyla hesaplanır.
3. Yanıt: dil modeli yalnızca bu hesaplanmış bilgilere dayanarak yanıtı yazar.
Hazır sorular dil modeli olmadan, aynı hesaplarla yanıtlanır.
"""

import datetime as dt
import difflib
import json
import re

import pandas as pd
import streamlit as st

from src.config import (CUSTOM_PERIOD, PAGE_FORECAST, PAGE_MARKETING, PAGE_NOTES, PAGE_SALES, PAGE_SUMMARY, PAGE_SUPPLY,
                        PERIODS, SEGMENTS, WEEKDAYS_TR)
from src.data_loader import (category_tree, load_category_forecasts, load_churn, load_cleaning_report, load_data,
                             load_forecast)
from src.filters import Filters, apply_filters, comparison_label, describe, period_name, previous_period
from src.formatting import fmt_number, fmt_pct, fmt_tl, tr_lower
from src.metrics import (abc_xyz, category_movers, city_table, cross_sell, customer_discounts, customer_flow,
                         inactive_customers, kpis, penetration, segment_profiles, top_titles, weekday_share)
from src.rfm import rfm_summary, rfm_table

TOPICS = ["Genel", "Satış ve Müşteri", "Pazarlama", "Ürün ve Tedarik", "Tahmin", "Veri"]
TOPIC_LINK = {"Genel": ("Yönetici Özeti", None, PAGE_SUMMARY), "Satış ve Müşteri": ("Satış ve Müşteri", "Kayıp Riski", PAGE_SALES),
              "Pazarlama": ("Pazarlama ve Segmentler", "Segment Profilleri", PAGE_MARKETING),
              "Ürün ve Tedarik": ("Ürün ve Tedarik", "ABC-XYZ Önceliklendirme", PAGE_SUPPLY),
              "Tahmin": ("Tahmin", "Haftalık Tahmin", PAGE_FORECAST), "Veri": ("Veri Notları", "Temizleme ve Kontrol Listesi", PAGE_NOTES)}
BREAKDOWNS = {"il": "City", "ana_kategori": "Main_Category", "alt_kategori": "Category_Standardized",
              "segment": "Segment", "ay": "InvoiceMonth", "ceyrek": "Quarter"}


# --- Kapsam -------------------------------------------------------------------------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", tr_lower(str(text))).strip()


def _match(values, allowed: list[str]) -> tuple[list[str], list[str]]:
    """Değerleri geçerli listeyle eşler: birebir (büyük/küçük harf duyarsız) ya da çok yakın yazım.
    Dönüş: (eşlenenler, tanınmayanlar)."""
    lookup = {_norm(a): a for a in allowed}
    found, unknown = [], []
    for v in values or []:
        key = _norm(v)
        if key in lookup:
            found.append(lookup[key])
            continue
        close = difflib.get_close_matches(key, list(lookup), n=1, cutoff=0.82)
        (found.append(lookup[close[0]]) if close else unknown.append(str(v)))
    return list(dict.fromkeys(found)), unknown


def build_scope(plan: dict, page_f: Filters) -> tuple[Filters, str, list[str]]:
    """Çözümlenen kapsamı doğrular; dönem yoksa sayfadaki dönemi kullanır.
    Dönüş: (filtre, dönemin kaynağı, tanınmayan değerler)."""
    df, _ = load_data()
    tree = category_tree()
    unknown = []
    period, source = page_f.period, "sayfadaki dönem"
    start, end = page_f.start, page_f.end
    if plan.get("donem") in PERIODS:
        period, source = plan["donem"], "sorudan"
        start, end = PERIODS[period]
    elif plan.get("baslangic") and plan.get("bitis"):
        try:
            lo, hi = df["InvoiceDate"].min().date(), df["InvoiceDate"].max().date()
            start = max(dt.date.fromisoformat(plan["baslangic"]), lo)
            end = min(dt.date.fromisoformat(plan["bitis"]), hi)
            if start <= end:
                period, source = CUSTOM_PERIOD, "sorudan"
            else:
                start, end = page_f.start, page_f.end
        except ValueError:
            pass
    cities, u1 = _match(plan.get("iller"), sorted(df["City"].unique()))
    mains, u2 = _match(plan.get("ana_kategoriler"), list(tree))
    subs, u3 = _match(plan.get("alt_kategoriler"), sorted({s for v in tree.values() for s in v}))
    segs, u4 = _match(plan.get("segmentler"), SEGMENTS)
    unknown = u1 + u2 + u3 + u4
    return Filters(period, start, end, tuple(cities), tuple(mains), tuple(segs), tuple(subs)), source, unknown


def scope_text(f: Filters, source: str) -> str:
    return f"{period_name(f)} ({source}); " + describe(f).split("; ", 1)[1]


# --- Konuya göre hesaplanmış bilgiler ----------------------------------------------------
def _frames(f: Filters):
    df, _ = load_data()
    cur = apply_filters(df, f)
    prev_f = previous_period(f, df["InvoiceDate"].min().date())
    prev = apply_filters(df, prev_f) if prev_f else None
    return df, cur, prev_f, (prev if prev is not None and not prev.empty else None)


def _move(cur_v: float, prev_v: float) -> str:
    if not prev_v:
        return ""
    ch = cur_v / prev_v - 1
    return f" ({'+' if ch >= 0 else '−'}{fmt_pct(abs(ch))})"


@st.cache_data(show_spinner="Yanıt için hesaplanıyor...")
def facts(topic: str, f: Filters) -> list[str]:
    """Konunun bilgilerini seçili kapsam için cümleler hâlinde döndürür (dil modeline ve hazır yanıtlara girdi)."""
    df, cur, prev_f, prev = _frames(f)
    if cur.empty and topic not in ("Veri",):
        return ["Bu kapsamda işlem yok."]
    out = []
    comp = comparison_label(f) if prev is not None else ""
    if topic == "Genel":
        k = kpis(cur)
        pk = kpis(prev) if prev is not None else None
        out.append(f"Net ciro {fmt_tl(k['revenue'])}" + (_move(k['revenue'], pk['revenue']) + f" {comp}" if pk else "") + ".")
        out.append(f"Fatura sayısı {fmt_number(k['invoices'])}" + (_move(k['invoices'], pk['invoices']) if pk else "")
                   + f"; ortalama fatura tutarı {fmt_tl(k['avg_invoice'])}" + (_move(k['avg_invoice'], pk['avg_invoice']) if pk else "")
                   + f"; alım yapan müşteri {fmt_number(k['customers'])}" + (_move(k['customers'], pk['customers']) if pk else "") + ".")
        if prev is not None:
            m = category_movers(cur, prev)
            if not m.empty:
                out.append("En çok değişen alt kategoriler: " + "; ".join(
                    f"{c} {'+' if r['diff'] >= 0 else '−'}{fmt_tl(abs(r['diff']))}" for c, r in m.iterrows()) + ".")
        seg = cur.groupby("Segment", observed=False)["Revenue"].sum().reindex(SEGMENTS).fillna(0)
        out.append("Segmentlerin ciro payı: " + "; ".join(f"{s} {fmt_pct(v / seg.sum())}" for s, v in seg.items()) + ".")
    elif topic == "Satış ve Müşteri":
        if prev is not None:
            scope = apply_filters(df, f, ignore=("period",))
            fl = customer_flow(scope, cur, prev, f.start)
            ina = inactive_customers(cur, prev)
            out.append(f"Müşteri hareketi ({period_name(prev_f)} → {period_name(f)}): {fl['prev']} → {fl['cur']}; "
                       f"hareketsiz {fl['inactive']}, geri dönen {fl['back']}, yeni {fl['new']}.")
            if not ina.empty:
                out.append(f"Hareketsiz müşterilerin önceki dönem cirosu {fmt_tl(ina['revenue'].sum())}; en büyükleri: " + "; ".join(
                    f"{cid} ({r.city}, {fmt_tl(r.revenue)})" for cid, r in ina.head(3).iterrows()) + ".")
        hist = apply_filters(df, f, ignore=("period", "category"))
        hist = hist[hist["InvoiceDate"] <= pd.Timestamp(f.end)]
        summ = rfm_summary(rfm_table(hist, pd.Timestamp(f.end)))
        if not summ.empty:
            out.append("RFM segmentleri (müşteri, ciro payı): " + "; ".join(
                f"{s} {fmt_number(r.customers)}, {fmt_pct(r.share)}" for s, r in summ.iterrows()) + ".")
        scores, _ = load_churn()
        cust = df.drop_duplicates("CustomerID").set_index("CustomerID")[["City", "Segment"]]
        keep = pd.Series(True, index=cust.index)
        if f.cities:
            keep &= cust["City"].isin(f.cities)
        if f.segments:
            keep &= cust["Segment"].isin(f.segments)
        risk = scores[scores.index.isin(cust.index[keep])]
        out.append(f"Kayıp riski (Ocak–Mart 2021 tahmini, dönemden bağımsız): riskteki ciro {fmt_tl(risk['risk_revenue'].sum())}; "
                   "en yüksek: " + "; ".join(f"{cid} ({r.city}, olasılık {fmt_pct(r.probability, 0)}, riskteki ciro "
                                             f"{fmt_tl(r.risk_revenue)})" for cid, r in risk.head(3).iterrows()) + ".")
        ct = city_table(cur, prev, n=5)
        out.append("Ciroya göre ilk iller: " + "; ".join(
            f"{c} {fmt_tl(r.revenue)}" + (f" ({'+' if r.change >= 0 else '−'}{fmt_pct(abs(r.change))})"
                                          if "change" in ct and pd.notna(r.get("change")) else "")
            for c, r in ct.iterrows()) + ".")
    elif topic == "Pazarlama":
        all_seg = apply_filters(df, f, ignore=("segment",))
        prof = segment_profiles(all_seg, f.end)
        out.append("Segmentler (2020 yıl sonu davranışına göre; bu dönemde alım yapan müşteri, ciro payı): " + "; ".join(
            f"{s} {fmt_number(prof.loc['customers', s])}, {fmt_pct(prof.loc['share', s])}" for s in SEGMENTS
            if pd.notna(prof.loc['customers', s])) + ".")
        w = 1 - cur["Revenue"].sum() / cur["ListValue"].sum()
        line = f"Ağırlıklı ortalama iskonto {fmt_pct(w)}"
        if prev is not None:
            pw = 1 - prev["Revenue"].sum() / prev["ListValue"].sum()
            line += f" (önceki dönem {fmt_pct(pw)})"
        cd = customer_discounts(cur)
        out.append(line + f"; müşteri bazında ortanca {fmt_pct(cd['discount'].median())}.")
        if len(cd) >= 5:
            cd["g"] = pd.qcut(cd["revenue"].rank(method="first"), 5, labels=False)
            g = cd.groupby("g")[["revenue", "list_value"]].sum()
            q = 1 - g["revenue"] / g["list_value"]
            out.append(f"İskonto: cirosu en büyük %20'lik müşteri grubunda {fmt_pct(q.iloc[4])}, en küçük grupta {fmt_pct(q.iloc[0])}.")
        rate, missing = penetration(apply_filters(df, f, ignore=("segment", "category")))
        t = cross_sell(rate, missing)
        if not t.empty:
            out.append("Çapraz satış fırsatları (kategoriyi almayan müşteri): " + "; ".join(
                f"{r.segment} – {r.category}: {fmt_number(r.missing)} müşteri (alım oranı {fmt_pct(r.rate, 0)}, "
                f"Çekirdek Kitabevleri'nde {fmt_pct(r.core_rate, 0)})" for r in t.head(3).itertuples()) + ".")
    elif topic == "Ürün ve Tedarik":
        out.append(f"Satılan adet {fmt_number(cur['Quantity'].sum())}, satılan farklı ürün {fmt_number(cur['StockCode'].nunique())}.")
        sh = weekday_share(cur)
        day = int(sh.idxmax())
        out.append(f"En yoğun gün {tr_lower(WEEKDAYS_TR[day])} (satılan adetin {fmt_pct(sh[day])} kadarı); "
                   f"salı–cuma ortalaması {fmt_pct(sh.iloc[1:5].mean())}.")
        scope_all = df
        if f.categories:
            scope_all = scope_all[scope_all["Main_Category"].isin(f.categories)]
        if f.subcategories:
            scope_all = scope_all[scope_all["Category_Standardized"].isin(f.subcategories)]
        sku = abc_xyz(scope_all)
        az = sku[(sku["abc"] == "A") & (sku["xyz"] == "Z")]
        out.append(f"ABC-XYZ (2020 tamamı, talep ve ciro önceliklendirmesi; stok verisi yok): A sınıfında "
                   f"{fmt_number((sku['abc'] == 'A').sum())} ürün cironun %80'ini getiriyor; yakın takip gerektiren AZ "
                   f"hücresinde {fmt_number(len(az))} ürün (cironun {fmt_pct(az['revenue'].sum() / sku['revenue'].sum())} kadarı).")
        tt = top_titles(cur, 3)
        out.append("En çok satan başlıklar: " + "; ".join(f"{t} ({fmt_number(r.quantity)} adet)" for t, r in tt.iterrows()) + ".")
        u = load_forecast(f.cities, f.categories, f.segments, "Quantity", 8, True, f.subcategories)
        if u["enough_data"]:
            out.append(f"Adet tahmini (4 Ocak – 28 Şubat 2021): {fmt_number(u['total'])} adet; yöntem {tr_lower(u['best'])}.")
    elif topic == "Tahmin":
        for value, unit in [("Revenue", "TL"), ("Quantity", "adet")]:
            r = load_forecast(f.cities, f.categories, f.segments, value, 8, True, f.subcategories)
            fmt = fmt_tl if unit == "TL" else (lambda v: f"{fmt_number(v)} adet")
            if not r["enough_data"]:
                out.append(f"{'Ciro' if unit == 'TL' else 'Adet'} tahmini: yeterli veri yok ({r['active_weeks']} hafta).")
                continue
            t = r["table"]
            out.append(f"{'Ciro' if unit == 'TL' else 'Adet'} tahmini (4 Ocak – 28 Şubat 2021, dönem filtresinden bağımsız): "
                       f"{fmt(r['total'])}, %80 aralığı {fmt(r['total_lo'])} – {fmt(r['total_hi'])}; seçilen yöntem "
                       f"{tr_lower(r['best'])}; kayan doğrulama MAPE {fmt_pct(t.loc[r['best'], 'mape'])} "
                       f"(naive {fmt_pct(t.loc['Naive', 'mape'])}); son test MAPE {fmt_pct(r['test'][r['best']])}.")
        cats = load_category_forecasts(f.cities, f.categories, f.segments, subcategories=f.subcategories)
        if not cats.empty and "signal" in cats:
            out.append("Kategori tahmin sinyalleri: " + "; ".join(f"{c.category}: {c.signal}" for c in cats.itertuples() if c.enough) + ".")
        out.append("Tahmine dayalı öneriler yalnızca seçilen model naive referansını geçtiğinde üretilir.")
    elif topic == "Veri":
        rep = load_cleaning_report()
        out.append(f"Ham veri {fmt_number(rep['ham_satir'])} satır; temiz veri {fmt_number(rep['temiz_satir'])} satır.")
        for s in rep["adimlar"]:
            if "silinen_satir" in s:
                out.append(f"Silinen: {s['adim']} {fmt_number(s['silinen_satir'])} satır ({s['gerekce']}).")
            elif "kontrole_ayrilan" in s:
                out.append(f"Kontrol listesine ayrılan: {s['adim']} {fmt_number(s['kontrole_ayrilan'])} satır.")
        c = rep.get("kategori", {})
        if c:
            out.append(f"Kategoriler: {c['original_categories']} orijinal etiket {c['standardized_categories']} alt kategoriye ve "
                       "15 ana kategoriye eşlendi; İngilizce etiketler çevrildi, eşdeğerler birleştirildi.")
        out.append("Yöntemler: k-ortalamalar segmentasyonu, RFM (R ve FM puanı), lojistik regresyonla kayıp riski, "
                   "ABC-XYZ önceliklendirmesi, haftalık satış tahmini (naive, doğrusal trend, üstel düzeltme; kayan doğrulama).")
        out.append("Veri yalnızca 2020'yi kapsar; stok, maliyet, iade ve yayınevi bilgisi yoktur.")
    return out


@st.cache_data(show_spinner=False)
def breakdown(f: Filters, dim: str, n: int = 10) -> list[str]:
    """İstenen kırılıma göre ciro tablosu (önceki döneme göre değişimle)."""
    df, cur, _, prev = _frames(f)
    col = BREAKDOWNS.get(dim)
    if col is None or cur.empty:
        return []
    key = (lambda d: d["InvoiceDate"].dt.quarter.map(lambda q: f"{q}. çeyrek")) if col == "Quarter" else \
          (lambda d: d["InvoiceDate"].dt.month.map(lambda m: f"{m:02d}. ay")) if col == "InvoiceMonth" else (lambda d: d[col])
    g = cur.groupby(key(cur), observed=True)["Revenue"].sum().sort_values(ascending=False)
    pg = prev.groupby(key(prev), observed=True)["Revenue"].sum() if prev is not None else None
    lines = []
    for name, v in g.head(n).items():
        ch = "" if pg is None or not pg.get(name) else f", {'+' if v >= pg[name] else '−'}{fmt_pct(abs(v / pg[name] - 1))}"
        lines.append(f"{name}: {fmt_tl(v)} (pay {fmt_pct(v / g.sum())}{ch})")
    return [f"Kırılım ({dim.replace('_', ' ')}): " + "; ".join(lines) + "."]


# --- Hazır sorular -------------------------------------------------------------------------
def _pick(lines: list[str], *keys: str) -> str:
    found = [x for x in lines if any(x.startswith(k) for k in keys)]
    return " ".join(found) if found else "Bu kapsamda yanıt için yeterli veri yok."


PRESETS = {
    "Genel": {"Bu dönemin özeti nedir?": lambda L: " ".join(L[:2]),
              "Cironun değişimini ne açıklıyor?": lambda L: _pick(L, "Fatura sayısı", "Net ciro"),
              "En çok değişen kategoriler hangileri?": lambda L: _pick(L, "En çok değişen")},
    "Satış ve Müşteri": {"Kaç müşteri hareketsiz kaldı?": lambda L: _pick(L, "Müşteri hareketi", "Hareketsiz"),
                         "Kayıp riski en yüksek müşteriler kim?": lambda L: _pick(L, "Kayıp riski"),
                         "En değerli müşteri grubu hangisi?": lambda L: _pick(L, "RFM"),
                         "İllerin durumu nasıl?": lambda L: _pick(L, "Ciroya göre ilk iller")},
    "Pazarlama": {"Hangi segmente kampanya yapmalıyız?": lambda L: _pick(L, "Çapraz satış"),
                  "İskonto büyük müşterilerde daha mı yüksek?": lambda L: _pick(L, "İskonto:"),
                  "Ortalama iskonto ne kadar?": lambda L: _pick(L, "Ağırlıklı ortalama iskonto"),
                  "Segmentlerin payı ne?": lambda L: _pick(L, "Segmentler")},
    "Ürün ve Tedarik": {"Hangi ürünler yakın takip gerektiriyor?": lambda L: _pick(L, "ABC-XYZ"),
                        "En yoğun gün hangisi?": lambda L: _pick(L, "En yoğun gün"),
                        "En çok satan başlıklar hangileri?": lambda L: _pick(L, "En çok satan"),
                        "Önümüzdeki 8 haftada kaç adet bekleniyor?": lambda L: _pick(L, "Adet tahmini")},
    "Tahmin": {"Önümüzdeki 8 haftada ne bekleniyor?": lambda L: _pick(L, "Ciro tahmini"),
               "Model ne kadar güvenilir?": lambda L: _pick(L, "Ciro tahmini", "Tahmine dayalı"),
               "Hangi kategoride değişim bekleniyor?": lambda L: _pick(L, "Kategori tahmin")},
    "Veri": {"Neden bazı satırlar silindi?": lambda L: _pick(L, "Silinen", "Kontrol listesine"),
             "Kategoriler nasıl standartlaştırıldı?": lambda L: _pick(L, "Kategoriler"),
             "Hangi yöntemler kullanıldı?": lambda L: _pick(L, "Yöntemler")},
}


def preset_answer(topic: str, question: str, page_f: Filters) -> str:
    f = Filters(page_f.period, page_f.start, page_f.end)  # hazır sorular: sayfadaki dönem, diğer filtreler yok
    body = PRESETS[topic][question](facts(topic, f))
    name, tab, _ = TOPIC_LINK[topic]
    return (f"**Kapsam:** {scope_text(f, 'sayfadaki dönem')}\n\n{body}\n\n"
            f"*Ayrıntı: {name}{' → ' + tab if tab else ''}*")


# --- Dil modeli için çözümleme ------------------------------------------------------------
def planner_prompt() -> str:
    tree = category_tree()
    df, _ = load_data()
    return (
        "Kullanıcının sorusundan kapsamı çıkar ve YALNIZCA tek bir JSON nesnesi döndür; açıklama yazma.\n"
        "Alanlar:\n"
        f'- "konu": şunlardan biri: {TOPICS + ["kapsam_disi"]}. Panelin verileriyle ilgisi olmayan istekler "kapsam_disi".\n'
        f'- "donem": soruda geçiyorsa şunlardan biri: {list(PERIODS)}; geçmiyorsa null.\n'
        '- "baslangic", "bitis": soruda ay ya da tarih aralığı geçiyorsa "YYYY-AA-GG" (veri yalnızca 2020); yoksa null.\n'
        f'- "iller": soruda geçen iller (liste). Geçerli değerler: {sorted(df["City"].unique())}\n'
        f'- "ana_kategoriler": soruda geçen ana kategoriler. Geçerli değerler: {list(tree)}\n'
        '- "alt_kategoriler": soruda geçen alt kategoriler (ör. Polisiye, Türkiye Roman). Geçerli değerler: '
        f'{sorted({s for v in tree.values() for s in v})}\n'
        f'- "segmentler": soruda geçen müşteri segmentleri. Geçerli değerler: {SEGMENTS}\n'
        f'- "kirilim": karşılaştırma ya da dağılım isteniyorsa şunlardan biri: {list(BREAKDOWNS)}; yoksa null.\n'
        "Soruda geçmeyen hiçbir değeri ekleme; emin olmadığın alanı boş bırak.")


def parse_plan(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        plan = json.loads(m.group(0))
        return plan if isinstance(plan, dict) else {}
    except json.JSONDecodeError:
        return {}


def answer_context(question: str, plan: dict, page_f: Filters) -> tuple[str, str]:
    """Çözümlenen plana göre bağlam metni ve ayrıntı bağlantısı üretir."""
    f, source, unknown = build_scope(plan, page_f)
    topic = plan.get("konu") if plan.get("konu") in TOPICS else "Genel"
    lines = facts(topic, f)
    if topic != "Genel":
        lines = facts("Genel", f)[:2] + lines
    if plan.get("kirilim") in BREAKDOWNS:
        lines += breakdown(f, plan["kirilim"])
    if unknown:
        lines.append(f"Tanınmayan değerler (veride yok ya da yazımı farklı): {', '.join(unknown)}.")
    name, tab, _ = TOPIC_LINK[topic]
    ctx = (f"KAPSAM: {scope_text(f, source)}\n"
           f"KONU: {topic}\n"
           "HESAPLANMIŞ BİLGİLER:\n" + "\n".join(f"- {x}" for x in lines) +
           f"\nAYRINTI SAYFASI: {name}{' → ' + tab if tab else ''}")
    return ctx, f"{name}{' → ' + tab if tab else ''}"

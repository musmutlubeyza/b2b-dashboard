"""
Veri hazırlama modülü.

Ham Excel dosyasını okur, temizler, türetilmiş değişkenleri ekler ve
sonucu uygulamanın hızlı okuyabileceği parquet formatında kaydeder.
Her temizleme adımı bir rapora yazılır; bu rapor dashboard'daki
"Veri Notları" sayfasında gösterilecek.

Çalıştırma (proje kök klasöründen, bir kez):
    python -m src.data_prep
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from src.categories import apply_hierarchy
from src.city_names import CITY_NAMES

# --- Dosya yolları ---------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "B2B_Transaction_Data_.xlsx"
PROCESSED_DIR = ROOT / "data" / "processed"
PARQUET_PATH = PROCESSED_DIR / "transactions.parquet"
REPORT_PATH = PROCESSED_DIR / "cleaning_report.json"
CATEGORY_AUDIT_PATH = PROCESSED_DIR / "category_mapping.csv"

# --- Kurallar --------------------------------------------------------------
UNKNOWN_LABEL = "Belirtilmemiş"
MIN_LIST_PRICE = 1.0  # TL; bunun altındaki liste fiyatları yer tutucu (0,0001 gibi)
MAX_DISCOUNT = 0.90   # bunun üzerindeki iskontolar fiilen bedelsiz sevkiyat sayılır


# --- Yardımcı fonksiyonlar ------------------------------------------------
def fix_title(value) -> str:
    """Excel'in sayı/tarih/saate çevirdiği kitap adlarını metne döndürür.

    Örnekler: 1984 -> '1984', 1963-11-22 -> '22/11/63', 22:04 -> '22:04'
    """
    if isinstance(value, dt.datetime):  # pd.Timestamp da bu sınıfa dahil
        return value.strftime("%d/%m/%y")
    if isinstance(value, dt.time):
        return value.strftime("%H:%M")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def revenue_of(df: pd.DataFrame) -> float:
    """Ciro = adet x iskontolu birim fiyat (eksik adetler toplama girmez)."""
    return float((df["Quantity"] * df["NetPrice"]).sum())


# --- Ana adımlar -----------------------------------------------------------
def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """Ham Excel dosyasını okur (yaklaşık 30-40 sn sürer)."""
    return pd.read_excel(path, sheet_name="Transaction")


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Veriyi temizler; temiz tabloyu ve adım adım raporu döndürür."""
    df = raw.copy()
    steps: list[dict] = []

    def drop_rows(mask: pd.Series, step: str, reason: str) -> None:
        """Maskeye uyan satırları siler ve raporlar."""
        nonlocal df
        removed = int(mask.sum())
        df = df.loc[~mask].copy()
        steps.append({"adim": step, "silinen_satir": removed, "gerekce": reason})

    def log_fix(step: str, affected: int, note: str) -> None:
        """Satır silmeyen düzeltmeleri raporlar."""
        steps.append({"adim": step, "duzeltilen_satir": int(affected), "gerekce": note})

    # 1) Tip dönüşümleri ve metin düzeltmeleri
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], format="%Y-%m-%d")
    df["StockCode"] = df["StockCode"].astype("int64").astype(str)

    bad_titles = ~df["Description"].map(lambda v: isinstance(v, str))
    df["Description"] = df["Description"].map(fix_title)
    log_fix("Ürün adı tip düzeltmesi", bad_titles.sum(),
            "Excel'in sayı/tarih/saate çevirdiği başlıklar metne döndürüldü.")

    padded = df["Category"].notna() & (df["Category"] != df["Category"].str.strip())
    df["Category"] = df["Category"].str.strip()
    df["City"] = df["City"].str.strip()
    log_fix("Kategori boşluk temizliği", padded.sum(),
            "Sonunda boşluk olan kategori etiketleri birleştirildi.")

    # 2) Birebir tekrar eden satırlar
    drop_rows(df.duplicated(keep="first"), "Birebir tekrar eden satırlar",
              "Kalem numarası olmadığından ayırt edilemiyor; çift sayımı önlemek için silindi.")

    # 3) Geçersiz adet
    drop_rows(df["Quantity"].isna() | (df["Quantity"] <= 0), "Eksik veya sıfır adet",
              "Satış miktarı tanımsız; ciroya katkısı yok veya düzeltme kaydı.")

    # 4) Geçersiz fiyatlar
    drop_rows(df["NetPrice"] <= 0, "Sıfır veya negatif net fiyat",
              "Ücretsiz/düzeltme kayıtları; iskonto oranını bozuyor.")
    drop_rows(df["UnitPrice"] < MIN_LIST_PRICE, f"Liste fiyatı < {MIN_LIST_PRICE:.0f} TL",
              "Yer tutucu fiyatlar (ör. 0,0001 TL).")
    drop_rows(df["NetPrice"] / df["UnitPrice"] < 1 - MAX_DISCOUNT,
              f"İskonto > %{MAX_DISCOUNT * 100:.0f}",
              "Neredeyse bedelsiz sevkiyat (tek fatura); iskonto analizlerini çarpıtıyor.")

    # 5) Eksik il: silmek yerine etiketle (eksik kategori 6. adımda sınıflandırılır)
    missing = df["City"].isna()
    df["City"] = df["City"].fillna(UNKNOWN_LABEL)
    log_fix("City eksik değer", missing.sum(), f"'{UNKNOWN_LABEL}' olarak etiketlendi.")

    # İl adlarını resmi yazıma çevir (ISTANBUL -> İstanbul, IÇEL -> Mersin)
    known = df["City"].isin(CITY_NAMES.keys())
    df["City"] = df["City"].map(CITY_NAMES).fillna(df["City"])
    log_fix("İl adı standardizasyonu", known.sum(),
            "Büyük harf/ASCII yazımlar resmi il adlarına çevrildi (IÇEL -> Mersin, AFYON -> Afyonkarahisar).")

    df["Quantity"] = df["Quantity"].astype("int64")

    # 6) Kategori hiyerarşisi: standart alt kategori, ana kategori, eksik kategorilerin sınıflandırılması
    df, category_audit, category_report = apply_hierarchy(df)
    df = df.drop(columns="Category")
    log_fix("Kategori standardizasyonu", (category_audit["Mapping_Status"].isin(["Normalized", "Translated", "Merged"])
                                          * category_audit["Records"]).sum(),
            "Etiketler sadeleştirildi, İngilizce etiketler çevrildi, eşdeğer etiketler birleştirildi; "
            "ayrıntı category_mapping.csv dosyasında.")
    log_fix("Eksik kategori sınıflandırması", category_report["classified_missing"],
            "Onaylı ürün eşlemesi, ürün kodu ve ürün adı eşleştirmesiyle atandı.")

    # 6) Türetilmiş değişkenler
    df["Revenue"] = df["Quantity"] * df["NetPrice"]        # net ciro
    df["ListValue"] = df["Quantity"] * df["UnitPrice"]     # liste fiyatıyla değer
    df["DiscountRate"] = 1 - df["NetPrice"] / df["UnitPrice"]

    df["InvoiceMonth"] = df["InvoiceDate"].dt.to_period("M").dt.to_timestamp()
    df["InvoiceWeek"] = df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time  # haftanın pazartesisi
    df["Weekday"] = df["InvoiceDate"].dt.dayofweek                             # 0 = Pazartesi

    df["InvoiceSeries"] = df["InvoiceNo"].str[:3]                     # BAD, BSR, DPF ...
    df["CustomerPrefix"] = df["CustomerID"].str[0]                    # A, P, S, D
    df["ParentCustomerID"] = df["CustomerID"].str.split("-").str[0]   # alt hesap ekini at
    df["ProductType"] = df["StockCode"].str[:3].isin(["978", "979"]).map(
        {True: "Kitap", False: "Kitap dışı"})

    # 7) Bellek optimizasyonu: az sayıda farklı değer alan metin kolonları
    #    "category" tipine çevrilir (canlı ortamda bellek ~%40 azalır).
    #    Not: bu kolonlarla groupby yaparken observed=True kullanılmalı.
    for col in ["Category_Original", "Category_Standardized", "Main_Category", "Category_Assignment_Method",
                "Category_Status", "City", "InvoiceSeries", "CustomerPrefix", "ProductType"]:
        df[col] = df[col].astype("category")

    df = df.reset_index(drop=True)

    report = {
        "ham_satir": len(raw),
        "temiz_satir": len(df),
        "ham_ciro": round(revenue_of(raw), 2),
        "temiz_ciro": round(float(df["Revenue"].sum()), 2),
        "adimlar": steps,
        "kategori": category_report,
    }
    return df, report, category_audit


def main() -> None:
    print("Ham veri okunuyor...")
    raw = load_raw()
    df, report, category_audit = clean(raw)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_PATH, index=False)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    category_audit.to_csv(CATEGORY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    for s in report["adimlar"]:
        n = s.get("silinen_satir", s.get("duzeltilen_satir"))
        kind = "silindi" if "silinen_satir" in s else "düzeltildi"
        print(f"- {s['adim']}: {n:,} satır {kind}")
    print(f"Satır: {report['ham_satir']:,} -> {report['temiz_satir']:,}")
    print(f"Ciro:  {report['ham_ciro']:,.0f} -> {report['temiz_ciro']:,.0f} TL")
    print(f"Kaydedildi: {PARQUET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

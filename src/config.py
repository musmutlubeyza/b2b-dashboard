"""Proje genelinde kullanılan sabitler: dosya yolları, sayfalar, renkler, etiketler."""

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "transactions.parquet"
REPORT_PATH = ROOT / "data" / "processed" / "cleaning_report.json"

# --- Sayfa dosyaları (st.page_link ve st.navigation aynı yolları kullanır) ---
PAGE_SUMMARY = "app_pages/yonetici_ozeti.py"
PAGE_SALES = "app_pages/satis.py"
PAGE_MARKETING = "app_pages/pazarlama.py"
PAGE_SUPPLY = "app_pages/tedarik.py"
PAGE_FORECAST = "app_pages/tahmin.py"
PAGE_NOTES = "app_pages/veri_notlari.py"

# --- BookWise paleti: parlak kırmızı (#ED2024) ve açık lavanta (#FAEAFF) ---
# Marka kırmızısı grafik ve vurgularda kullanılır. Küçük metin, bağlantı ve düğmelerde okunabilirlik için
# biraz koyulaştırılmış tonları kullanılır (beyaz ve lavanta zeminde kontrast ≥ 4,5:1).
BRAND_RED, BRAND_LAVENDER = "#ED2024", "#FAEAFF"
HEADER_BG = BRAND_LAVENDER                 # üst çubuk: logodaki zemin
PRIMARY = BRAND_RED                        # ana çizgi ve vurgulanan çubuklar
PRIMARY_DARK = "#C8161C"                   # metin ve bağlantı
BUTTON_RED = "#D91A20"                     # beyaz yazılı düğmeler
PRIMARY_LIGHT = "#F7B3B5"                  # müşteri payı gibi ikincil çubuklar
ACCENT = "#7A3E8F"                         # mor: artışlar, ikinci seri
SECONDARY = "#DCC8EA"                      # vurgulanmayan sütunlar
COMPARE = "#8E7A99"                        # karşılaştırma çizgisi
SURFACE = "#FDF6FF"                        # filtre alanı ve tablo başlıkları
TEXT, MUTED, LINE = "#2A1F2D", "#6E5F73", "#EEE2F3"
GREEN, RED = "#2E6B45", "#B3161B"          # artış/azalış metinleri
KPI_TINTS = [(BRAND_LAVENDER, "#FFFFFF", BRAND_RED),
             ("#FFEDEE", "#FFFFFF", BRAND_RED),
             (BRAND_LAVENDER, "#FFFFFF", ACCENT),
             ("#FFEDEE", "#FFFFFF", ACCENT)]
FONT_BODY = "Plus Jakarta Sans, sans-serif"
FONT_HEAD = "Bricolage Grotesque, Plus Jakarta Sans, sans-serif"


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha:.2f})"


# --- Segmentler (sıra ve renk tüm grafiklerde aynı) ---
SEGMENTS = ["Çekirdek Kitabevleri", "Toplu Alıcılar", "Düzenli Küçük Alıcılar", "Uykudaki Müşteriler"]
SEGMENT_COLORS = dict(zip(SEGMENTS, [PRIMARY, ACCENT, "#B79CC8", "#D6CEDB"]))

# --- Dönemler ---
PERIODS = {
    "Tüm yıl 2020": (dt.date(2020, 1, 1), dt.date(2020, 12, 31)),
    "1. Çeyrek 2020": (dt.date(2020, 1, 1), dt.date(2020, 3, 31)),
    "2. Çeyrek 2020": (dt.date(2020, 4, 1), dt.date(2020, 6, 30)),
    "3. Çeyrek 2020": (dt.date(2020, 7, 1), dt.date(2020, 9, 30)),
    "4. Çeyrek 2020": (dt.date(2020, 10, 1), dt.date(2020, 12, 31)),
}
CUSTOM_PERIOD = "Özel aralık"
DEFAULT_PERIOD = "4. Çeyrek 2020"
PANDEMIC_BAND = (dt.date(2020, 3, 16), dt.date(2020, 6, 1))  # yaklaşık kısıtlama dönemi
SALES_GAP_WEEKS = ("2020-07-20", "2020-07-27")  # 22 Temmuz – 2 Ağustos: hiç fatura yok (kayıt boşluğu)
INACTIVE_DAYS = 90

# --- Türkçe etiketler ---
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
MONTHS_TR_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
WEEKDAYS_TR_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]  # ilk 3 harf Pazartesi/Pazar ve Cuma/Cumartesi'yi karıştırır

# --- Sayfa içi sekmeler (bağlantılar sekmeyi adıyla açtığı için tek yerde tanımlı) ---
TAB_PARAM = "sekme"
SALES_TABS = ["Müşteri Hareketi", "RFM Segmentleri", "Kayıp Riski", "İl Performansı"]
MARKETING_TABS = ["Segment Profilleri", "Kategori ve Çapraz Satış", "İskonto"]
SUPPLY_TABS = ["ABC-XYZ Önceliklendirme", "İş Yükü", "En Çok Satan Başlıklar"]
FORECAST_TABS = ["Haftalık Tahmin", "Model Karşılaştırması", "Kategori Tahminleri", "Sınırlılıklar"]
NOTES_TABS = ["Temizleme ve Kontrol Listesi", "Düzeltmeler", "Kategori Standardizasyonu", "Varsayımlar ve Sınırlılıklar",
              "Yöntemler ve Terimler", "Aksiyon Kuralları", "Filtre Davranışı"]

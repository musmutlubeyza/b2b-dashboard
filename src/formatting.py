"""Sayı, para ve tarih biçimlendirme (Türkçe: binlik ayıracı nokta, ondalık virgül)."""

import datetime as dt

from src.config import MONTHS_TR

# Türkçe alfabetik sıralama için harf sırası (Ç, Ğ, İ, Ö, Ş, Ü doğru yerde)
_TR_ALPHABET = "AaBbCcÇçDdEeFfGgĞğHhIıİiJjKkLlMmNnOoÖöPpQqRrSsŞşTtUuÜüVvWwXxYyZz"
_TR_ORDER = {ch: i for i, ch in enumerate(_TR_ALPHABET)}


def fmt_number(x: float, decimals: int = 0) -> str:
    """1234567.8 -> '1.234.567,8'"""
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_tl(x: float) -> str:
    """Tutarı okunabilir kısaltmayla yazar: '29,42 Mn TL', '623 TL'."""
    if abs(x) >= 1_000_000:
        return f"{fmt_number(x / 1_000_000, 2)} Mn TL"
    if abs(x) >= 10_000:
        return f"{fmt_number(x / 1_000, 1)} bin TL"
    return f"{fmt_number(x, 0)} TL"


def fmt_pct(x: float, decimals: int = 1) -> str:
    """0.392 -> '%39,2' (Türkçede yüzde işareti başa gelir)."""
    return f"%{fmt_number(x * 100, decimals)}"


def fmt_date(d: dt.date) -> str:
    """2020-03-16 -> '16 Mart 2020'"""
    return f"{d.day} {MONTHS_TR[d.month - 1]} {d.year}"


def tr_sort_key(text: str) -> list[int]:
    """sorted(..., key=tr_sort_key) ile Türkçe alfabeye göre sıralama."""
    return [_TR_ORDER.get(ch, 1000 + ord(ch)) for ch in str(text)]


# --- Türkçe büyük/küçük harf -------------------------------------------------
# Python'un str.lower/upper/title fonksiyonları Türkçeyi bilmez: "İ".lower() noktası ayrı
# bir "i̇" üretir, "iskonto".title() ise "Iskonto" olur. Bu fonksiyonlar Türkçe kurala uyar.
_TITLE_KEEP_LOWER = {"ve", "ile", "veya", "ya", "da", "de", "ki", "mi", "mı", "mu", "mü"}


def tr_lower(text: str) -> str:
    return str(text).replace("İ", "i").replace("I", "ı").lower()


def tr_upper(text: str) -> str:
    return str(text).replace("i", "İ").replace("ı", "I").upper()


def tr_capitalize_word(word: str) -> str:
    """Kelimenin ilk harfini Türkçe kurala göre büyütür; geri kalanına dokunmaz (SKU, RFM korunur)."""
    for i, ch in enumerate(word):
        if ch.isalpha():
            return word[:i] + tr_upper(ch) + word[i + 1:]
    return word


def tr_title(text: str) -> str:
    """Başlık düzeni: her kelime büyük harfle başlar; bağlaçlar (ve, ile, veya, de/da, ki, mi) küçük kalır."""
    words = str(text).split(" ")
    return " ".join(w if (i > 0 and tr_lower(w) in _TITLE_KEEP_LOWER) else tr_capitalize_word(w)
                    for i, w in enumerate(words))

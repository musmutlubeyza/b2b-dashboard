"""BookWise Intelligence Platform (B2B kitap dağıtım karar destek paneli): uygulamanın giriş noktası.

Çalıştırma (proje kök klasöründen):  streamlit run streamlit_app.py

Bu dosya ortak işleri yapar: sayfa ayarları, stil, üst gezinme, sabit filtre
çubuğu. Filtreler burada çizildiği için sayfa geçişlerinde korunur.
"""

import streamlit as st

from src.config import (DATA_PATH, PAGE_FORECAST, PAGE_MARKETING, PAGE_NOTES, PAGE_SALES,
                        PAGE_SUMMARY, PAGE_SUPPLY)
from src.data_loader import load_data
from src.filters import render_filter_bar
from src.style import inject_css

st.set_page_config(page_title="BookWise | Intelligence Platform", page_icon="assets/icon.png", layout="wide")
inject_css()

if not DATA_PATH.exists():
    st.error("Temiz veri dosyası bulunamadı. Proje klasöründe önce `python -m src.data_prep` komutunu çalıştırın.")
    st.stop()

st.logo("assets/logo.png", size="large")
df, _ = load_data()

pages = [
    st.Page(PAGE_SUMMARY, title="Yönetici Özeti", default=True),
    st.Page(PAGE_SALES, title="Satış ve Müşteri"),
    st.Page(PAGE_MARKETING, title="Pazarlama ve Segmentler"),
    st.Page(PAGE_SUPPLY, title="Ürün ve Tedarik"),
    st.Page(PAGE_FORECAST, title="Tahmin"),
    st.Page(PAGE_NOTES, title="Veri Notları"),
]
current = st.navigation(pages, position="top")
render_filter_bar(df, disabled=current.title == "Veri Notları")
current.run()

"""Veri Notları: temizleme adımları, varsayımlar, sınırlılıklar, yöntemler, aksiyon ve filtre kuralları.
Bu sayfa filtrelerden etkilenmez."""

import streamlit as st

from src.actions import Action
from src.chat import render_chat
from src.config import PAGE_NOTES
from src.data_loader import load_category_audit, load_churn, load_cleaning_report, load_data, load_forecast
from src.filters import describe
from src.formatting import fmt_number, fmt_pct, fmt_tl
from src.ui import action_cards, html_table, kpi_card, section_header

rep = load_cleaning_report()
_, silhouette = load_data()
_, churn = load_churn()
fc = load_forecast()
removed = rep["ham_satir"] - rep["temiz_satir"]

st.title("Veri Notları")
st.caption("Kaynak: B2B_Transaction_Data_.xlsx (Transaction sayfası). Temizleme kodu: src/data_prep.py.")

c = st.columns(4)
with c[0]:
    kpi_card(0, "Ham satır", fmt_number(rep["ham_satir"]), note="10 kolon, 2020 yılı fatura kalemleri")
with c[1]:
    kpi_card(1, "Temiz satır", fmt_number(rep["temiz_satir"]), note="Tüm analizlerde kullanılan")
with c[2]:
    kpi_card(2, "Silinen satır", fmt_number(removed), note=f"Ham verinin {fmt_pct(removed / rep['ham_satir'], 2)} kadarı")
with c[3]:
    kpi_card(3, "Ciroya etkisi", f"−{fmt_pct(1 - rep['temiz_ciro'] / rep['ham_ciro'], 2)}",
             note=f"{fmt_tl(rep['ham_ciro'])} → {fmt_tl(rep['temiz_ciro'])}")

main, side = st.columns([3.4, 1], gap="large")
with main:
    tabs = st.tabs(["Silinen satırlar", "Düzeltmeler", "Kategori standardizasyonu", "Varsayımlar ve sınırlılıklar",
                    "Yöntemler", "Aksiyon kuralları", "Filtre davranışı"])
    with tabs[0]:
        section_header("Silinen satırlar")
        st.caption("Adımlar bu sırayla uygulandı; sayılar her adımın kendi etkisini gösterir.")
        html_table(["Adım", "Satır", "Gerekçe"],
                   [[f"<b>{s['adim']}</b>", fmt_number(s["silinen_satir"]), s["gerekce"]] for s in rep["adimlar"] if "silinen_satir" in s],
                   ["left", "right", "left"])
    with tabs[1]:
        section_header("Düzeltmeler")
        st.caption("Bu adımlarda satır silinmedi; değerler düzeltildi ya da etiketlendi.")
        html_table(["Adım", "Satır", "Açıklama"],
                   [[f"<b>{s['adim']}</b>", fmt_number(s["duzeltilen_satir"]), s["gerekce"]] for s in rep["adimlar"] if "duzeltilen_satir" in s],
                   ["left", "right", "left"])
    with tabs[2]:
        cr = rep["kategori"]
        audit = load_category_audit()
        a, b = st.columns([1, 1.4], gap="large")
        with a:
            section_header("Kategori kalite raporu")
            methods = {"Existing Category": "Mevcut kategori", "Approved Product Mapping": "Onaylı ürün eşlemesi",
                       "StockCode Matching": "Ürün kodu eşleştirme", "Description Matching": "Ürün adı eşleştirme",
                       "Manual Review": "Manuel inceleme"}
            html_table(["Ölçü", "Değer"], [
                ["Orijinal kategori sayısı", fmt_number(cr["original_categories"])],
                ["Standart alt kategori sayısı", fmt_number(cr["standardized_categories"])],
                ["Birleştirilen etiket", fmt_number(cr["merged_labels"])],
                ["Kategorisi eksik kayıt (sınıflandırma öncesi)", fmt_number(cr["missing_before"])],
                ["Başarıyla sınıflandırılan eksik kayıt", fmt_number(cr["classified_missing"])],
                ["Çözülemeyen kayıt", fmt_number(cr["unresolved"])],
                ["İnceleme bekleyen kayıt (tartışmalı ana kategori)", fmt_number(cr["needs_review_records"])],
            ] + [[f"Atama yöntemi: {methods.get(k, k)}", fmt_number(v)] for k, v in cr["by_method"].items()],
                ["left", "right"])
        with b:
            section_header("Ana kategori dağılımı")
            dist = cr["main_distribution"]
            total = sum(v["records"] for v in dist.values())
            html_table(["Ana kategori", "Kayıt", "Pay", "Ürün"],
                       [[m, fmt_number(v["records"]), fmt_pct(v["records"] / total), fmt_number(v["products"])] for m, v in dist.items()],
                       ["left", "right", "right", "right"])
        section_header("Eşleme denetim tablosu")
        st.caption("Her orijinal etiketin standart adı, ana kategorisi ve eşleme durumu. Durumlar: Unchanged (değişmedi), "
                   "Normalized (yazım düzeltildi), Translated (çevrildi), Merged (eşdeğer etiketle birleşti), "
                   "Needs Review (ana kategori onay bekliyor).")
        st.dataframe(audit, height=260, hide_index=True)
        st.download_button("Denetim tablosunu indir (CSV)", audit.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "kategori_esleme.csv", "text/csv")
    with tabs[3]:
        a, b = st.columns(2, gap="large")
        with a:
            section_header("Varsayımlar")
            st.markdown(
                "- **NetPrice** iskonto sonrası birim satış fiyatı, **UnitPrice** liste fiyatı kabul edildi. NetPrice'ın KDV içerip içermediği veride belirtilmiyor.\n"
                "- **Ciro** = adet × NetPrice. **İskonto** = 1 − ciro ÷ liste değeri (ağırlıklı).\n"
                "- Fatura serileri (BAD, BSR, DPF, DPE, MUH) ve müşteri kod ön ekleri (A, P, S, D) yorumlanmadı.\n"
                "- Birebir aynı satırlar, kalem numarası olmadığı için çift kayıt kabul edildi.\n"
                "- Pandemi kısıtlamaları bandı yaklaşık bir aralıktır (16 Mart – 1 Haziran 2020).")
        with b:
            section_header("Sınırlılıklar")
            st.markdown(
                "- Veri yalnızca 2020'yi kapsıyor; geçen yılla karşılaştırma ve yıllık mevsimsellik yok.\n"
                "- Stok, maliyet, tedarik süresi ve iade bilgisi yok; kârlılık hesaplanamıyor.\n"
                "- Ürün düzeyinde talep çok seyrek (ortanca ürün yılda 4 gün satılıyor).\n"
                "- Faturalar kitabevlerinin toplu siparişleri; son tüketici tercihini yansıtmaz.\n"
                "- Çeyrekler arası farkın bir kısmı mevsimsel olabilir; tek yılla ayrıştırılamaz.")
    with tabs[4]:
        section_header("Kullanılan yöntemler")
        best = fc["best"]
        html_table(["Analiz", "Yöntem", "Parametreler ve sonuç", "Sayfa"], [
            ["<b>Segmentasyon</b>", "K-ortalamalar", f"k = 4; 6 değişken (log ölçek) standartlaştırıldı; silhouette {fmt_number(silhouette, 2)}", "Pazarlama"],
            ["<b>RFM</b>", "Son alım, sıklık, tutar için 1–5 dilim puanı", "R ve F puanlarından 7 segment; dönem sonuna kadarki geçmiş", "Satış"],
            ["<b>Kayıp riski</b>", "Lojistik regresyon", f"Kayıp: 92 gün alımsız. Zamansal test AUC {fmt_number(churn['auc_model'], 3)} "
             f"(son alım kuralı {fmt_number(churn['auc_rule'], 3)})", "Satış"],
            ["<b>ABC-XYZ</b>", "Kümülatif ciro payı; aylık talep değişkenliği", "A %80, B %95; X &lt; 0,5 ≤ Y &lt; 1,0 ≤ Z; 2020 tamamı", "Ürün ve Tedarik"],
            ["<b>Satış tahmini</b>", f"{best} (naive ve üstel düzeltmeyle yarıştı)",
             f"Aykırı haftalar Hampel filtresiyle sınırlandı; son 6 hafta doğrulama: MAPE {fmt_pct(fc['table'].loc[best, 'mape'])} "
             f"(naive {fmt_pct(fc['table'].loc['Naive', 'mape'])})", "Tahmin"],
            ["<b>Sohbet</b>", "Hazır sorular; yanıtlar sayfanın güncel hesaplarından üretilir", "Dil modeli isteğe bağlı (OpenRouter anahtarı eklenirse serbest soru açılır)", "Tüm sayfalar"],
        ], ["left", "left", "left", "left"])
    with tabs[5]:
        section_header("Aksiyon kuralları")
        st.caption("Paneldeki her öneri bu kurallardan biriyle üretilir; tahmine dayalı öneriler yalnızca model naive referansını geçerse gösterilir.")
        html_table(["Öneri", "Tetikleyici kural", "Departman", "Dayanak"], [
            ["<b>Geri kazanım</b>", "Önceki dönemde alıp seçili dönemde almayan müşteriler", "Satış", "Veri"],
            ["<b>Büyük müşteri teması</b>", "Önceki dönem cirosu en yüksek kaybedilen müşteri, 90 günden uzun süredir alım yoksa", "Satış", "Veri"],
            ["<b>Kayıp riski ataması</b>", "Kayıp olasılığı × 2020 cirosu en yüksek 20 müşteri", "Satış", "Tahmin"],
            ["<b>İkinci sipariş</b>", "İlk alımını seçili dönemde yapan müşteriler", "Satış", "Veri"],
            ["<b>Çapraz satış</b>", "Segmentte kategori alım oranı çekirdek segmentin yarısından az (uykudaki müşteriler hariç)", "Pazarlama", "Veri"],
            ["<b>İskonto incelemesi</b>", "Ağırlıklı iskontosu %35–45 bandının dışında kalan müşteriler", "Pazarlama", "Veri"],
            ["<b>Emniyet stoku</b>", "ABC-XYZ matrisinde AZ hücresindeki ürünler", "Tedarik", "Veri"],
            ["<b>Kapasite</b>", "Bir günün adet payı salı–cuma ortalamasının 1,5 katını aşıyor", "Tedarik", "Veri"],
            ["<b>Sipariş planı / hedef</b>", "Toplam ciro tahmini ve %80 aralığı", "Tedarik, Yönetim", "Tahmin"],
            ["<b>Kategori sinyali</b>", "Tahmin aralığı son 8 hafta ortalamasının tamamen üstünde ya da altında", "Tedarik, Pazarlama", "Tahmin"],
            ["<b>Model izleme</b>", "Gerçekleşen %80 aralığın dışına çıkarsa model yeniden kurulur", "Veri", "Tahmin"],
        ], ["left", "left", "left", "left"])
    with tabs[6]:
        section_header("Filtre davranışı")
        st.caption("Bir filtreyi yok sayan ya da yalnızca vurgulayan bölümlerin başlığında bunu belirten bir etiket bulunur.")
        S, V, B = "Süzer", "Vurgular", "Bağımsız"
        html_table(["Bölüm", "Dönem", "İl", "Ana ve alt kategori", "Segment"], [
            ["<b>KPI kartları</b>", S, S, S, S],
            ["<b>Haftalık ciro ve tahmin (Özet)</b>", "Süzer; tahmin yalnız yıl sonu dahilse", S, S, S],
            ["<b>Çeyreklere göre ciro</b>", V, S, S, S],
            ["<b>En çok değişen kategoriler</b>", S, S, "En az 3 seçimde", S],
            ["<b>Segment grafikleri ve profilleri</b>", S, S, S, V],
            ["<b>Müşteri hareketi</b>", "Süzer; önceki dönem gerekir", S, S, S],
            ["<b>RFM</b>", "Dönem sonuna kadarki geçmiş", S, B, S],
            ["<b>Kayıp riski</b>", "Bağımsız (yıl sonu)", S, B, S],
            ["<b>Penetrasyon ve çapraz satış</b>", S, S, B, V],
            ["<b>ABC-XYZ</b>", "Bağımsız (2020 tamamı)", B, S, B],
            ["<b>Tahmin sayfası</b>", "Bağımsız (tüm geçmiş)", S, S, S],
        ], ["left", "left", "left", "left", "left"])

with side:
    dup = next((s["silinen_satir"] for s in rep["adimlar"] if s["adim"].startswith("Birebir")), 0)
    action_cards([
        Action("Veri", "Fatura serilerinin ve müşteri ön eklerinin anlamını netleştir",
               "BAD, BSR, DPF, DPE, MUH ve A, P, S, D kodları şu an yalnızca filtre ve bağlam bilgisi.", PAGE_NOTES, "Varsayımlar"),
        Action("Veri", "NetPrice'ın KDV durumunu doğrula", "İskonto ve ciro yorumları bu varsayıma dayanıyor.", PAGE_NOTES, "Varsayımlar"),
        Action("Veri", "Faturalara kalem numarası eklenmesini iste",
               f"{fmt_number(dup)} tekrar eden satırın çift kayıt mı, ayrı kalem mi olduğu ayırt edilemiyor.", PAGE_NOTES, "Silinen satırlar"),
    ])

render_chat("notes", describe(st.session_state["filters"]),
            [f"Temizlik sonrası {fmt_number(removed)} satır çıkarıldı; ciroya etkisi −{fmt_pct(1 - rep['temiz_ciro'] / rep['ham_ciro'], 2)}.",
             f"En büyük kalem birebir tekrar eden {fmt_number(dup)} satır.",
             "Fiyat yorumu bir varsayıma dayanıyor: NetPrice'ın KDV durumu veride yok."],
            {"Neden bazı satırlar silindi?": "Silinen satırların çoğu birebir tekrar eden kayıtlar; kalanlar eksik adet, sıfır veya "
                                            "negatif fiyat, yer tutucu liste fiyatı ve neredeyse bedelsiz tek bir faturadan oluşuyor.",
             "Kategoriler nasıl standartlaştırıldı?": f"{rep['kategori']['original_categories']} orijinal etiket açık bir eşleme "
                                                    f"sözlüğüyle {rep['kategori']['standardized_categories']} alt kategoriye ve 15 ana "
                                                    "kategoriye bağlandı; İngilizce etiketler çevrildi, eşdeğerler birleştirildi.",
             "Hangi yöntemler kullanıldı?": "K-ortalamalar segmentasyonu, RFM, lojistik regresyonla kayıp riski, ABC-XYZ ve "
                                           "haftalık satış tahmini (naive, doğrusal trend ve üstel düzeltme yarıştırıldı)."})

"""Veri Notları: temizleme ve kontrol listesi, düzeltmeler, kategori standardizasyonu, varsayımlar,
sınırlılıklar, yöntemler, terimler, aksiyon ve filtre kuralları. Bu sayfa filtrelerden etkilenmez."""

import streamlit as st

from src.actions import Action
from src.config import NOTES_TABS, PAGE_NOTES, SEGMENTS
from src.data_loader import (load_category_audit, load_churn, load_cleaning_report, load_data, load_forecast,
                             load_review_records)
from src.formatting import fmt_number, fmt_pct, fmt_tl, tr_lower
from src.ui import action_cards, html_table, kpi_card, page_tabs, section_header

rep = load_cleaning_report()
df, silhouette = load_data()
_, churn = load_churn()
fc = load_forecast()
review = load_review_records()
dup = next(s for s in rep["adimlar"] if "silinen_satir" in s)
aside = [s for s in rep["adimlar"] if "kontrole_ayrilan" in s]
n_aside = sum(s["kontrole_ayrilan"] for s in aside)

st.title("Veri Notları")
st.caption("Kaynak: B2B_Transaction_Data_.xlsx (Transaction sayfası). Temizleme kodu: src/data_prep.py.")

c = st.columns(4)
with c[0]:
    kpi_card(0, "Ham satır", fmt_number(rep["ham_satir"]), note="10 kolon, 2020 yılı fatura kalemleri")
with c[1]:
    kpi_card(1, "Temiz satır", fmt_number(rep["temiz_satir"]), note="Tüm analizlerde kullanılan")
with c[2]:
    kpi_card(2, "Silinen tekrar", fmt_number(dup["silinen_satir"]),
             note=f"Birebir tekrar eden satırlar; ciroya etkisi −{fmt_pct(dup['etki']['ciro'] / rep['ham_ciro'], 2)}")
with c[3]:
    kpi_card(3, "Kontrole ayrılan", fmt_number(n_aside),
             note="Silinmedi; hesaplamalara girmez, kaynak sistemde doğrulanmalı")


def impact_row(s: dict, count_key: str) -> list[str]:
    e = s["etki"]
    gone = ", ".join(f"{e[k]} {t}" for k, t in [("fatura", "fatura"), ("musteri", "müşteri"), ("urun", "ürün")] if e[k]) or "Yok"
    return [f"<b>{s['adim']}</b>", fmt_number(s[count_key]), fmt_tl(e["ciro"]), fmt_pct(e["ciro"] / rep["ham_ciro"], 2),
            fmt_number(e["adet"]), gone, s["gerekce"]]


headers = ["Adım", "Satır", "Ciro etkisi", "Ciro payı", "Adet etkisi", "Tamamen düşen", "Gerekçe"]
align = ["left", "right", "right", "right", "right", "left", "left"]
main, side = st.columns([3.4, 1], gap="large")
with main:
    tabs = page_tabs(NOTES_TABS, "tabs_notes")
    with tabs[0]:
        section_header("Silinen tekrarlar")
        st.caption("Yalnızca birebir tekrar eden satırlar silindi. \"Tamamen düşen\": kalan veride hiç kaydı kalmayan "
                   "fatura, müşteri ya da ürün sayısı (hassasiyet analizi).")
        html_table(headers, [impact_row(dup, "silinen_satir")], align)
        section_header("Kontrol listesi", badge="Hesaplamalara girmez")
        st.caption("Bu kayıtlar büyük olasılıkla hata değil, açıklama bekleyen işlemler (düzeltme kaydı, bedelsiz sevkiyat, "
                   "yer tutucu fiyat). Silinmediler; ayrı bir dosyada gerekçeleriyle saklanıyor. Sonuçlara etkileri "
                   "ihmal edilebilir düzeyde: dahil edilseler ağırlıklı ortalama iskonto değişmiyor ve hiçbir müşteri "
                   "analizden düşmüyor.")
        html_table(headers, [impact_row(s, "kontrole_ayrilan") for s in aside], align)
        if not review.empty:
            cols = ["Kontrol_Gerekcesi", "InvoiceNo", "InvoiceDate", "CustomerID", "StockCode", "Description",
                    "Quantity", "NetPrice", "UnitPrice"]
            st.download_button(f"Kontrol listesini indir ({fmt_number(len(review))} kayıt, CSV)",
                               review[[c for c in cols if c in review]].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                               "kontrol_listesi.csv", "text/csv", type="primary")
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
        q1 = set(df.loc[df["InvoiceDate"].dt.quarter == 1, "CustomerID"].unique())
        dormant = df.loc[df["Segment"] == SEGMENTS[3], "CustomerID"].unique()
        a, b = st.columns(2, gap="large")
        with a:
            section_header("Varsayımlar")
            st.markdown(
                "- **NetPrice** iskonto sonrası birim satış fiyatı, **UnitPrice** liste fiyatı kabul edildi. NetPrice'ın KDV içerip içermediği veride belirtilmiyor.\n"
                "- **Ciro** = adet × NetPrice. **İskonto** = 1 − ciro ÷ liste değeri (ağırlıklı).\n"
                "- Fatura serileri (BAD, BSR, DPF, DPE, MUH) ve müşteri kod ön ekleri (A, P, S, D) yorumlanmadı.\n"
                "- Birebir aynı satırlar, kalem numarası olmadığı için çift kayıt kabul edildi.\n"
                "- Pandemi kısıtlamaları bandı yaklaşık bir aralıktır (16 Mart – 1 Haziran 2020).\n"
                "- 22 Temmuz – 2 Ağustos arasında hiç fatura yok; bu dönem talep düşüşü değil, kayıt boşluğu kabul edildi.")
        with b:
            section_header("Sınırlılıklar")
            st.markdown(
                "- Veri yalnızca 2020'yi kapsıyor; geçen yılla karşılaştırma ve yıllık mevsimsellik yok.\n"
                "- Stok, maliyet, tedarik süresi, iade ve yayınevi bilgisi yok; kârlılık ve stok miktarı hesaplanamıyor. "
                "ABC-XYZ bu yüzden stok politikası değil, talep ve ciro önceliklendirmesi olarak sunuluyor.\n"
                f"- Müşteri segmentleri 2020 yıl sonu davranışından belirlendi ve geçmiş dönemlerde de bu etiketler "
                f"kullanılıyor. Örneğin {SEGMENTS[3]} segmentindeki {fmt_number(len(dormant))} müşterinin "
                f"{fmt_number(len(set(dormant) & q1))}'i 1. çeyrekte alım yaptı; o dönemde uykuda değillerdi.\n"
                "- Ürün düzeyinde talep çok seyrek (ortanca ürün yılda 4 gün satılıyor).\n"
                "- Faturalar kitabevlerinin toplu siparişleri; son tüketici tercihini yansıtmaz.\n"
                "- Çeyrekler arası farkın bir kısmı mevsimsel olabilir; tek yılla ayrıştırılamaz.")
    with tabs[4]:
        section_header("Kullanılan yöntemler")
        best = fc["best"]
        html_table(["Analiz", "Yöntem", "Parametreler ve sonuç", "Sayfa"], [
            ["<b>Segmentasyon</b>", "K-ortalamalar", f"k = 4; 6 değişken (log ölçek) standartlaştırıldı; silhouette {fmt_number(silhouette, 2)}; 2020 yıl sonu", "Pazarlama"],
            ["<b>RFM</b>", "Son alım, sıklık, tutar için 1–5 dilim puanı", "Segmentler R puanı ile FM puanından (F ve M ortalaması) üretilir; dönem sonuna kadarki geçmiş", "Satış"],
            ["<b>Kayıp riski</b>", "Lojistik regresyon", f"Kayıp: 92 gün alımsız. Zamansal test AUC {fmt_number(churn['auc_model'], 3)} "
             f"(son alım kuralı {fmt_number(churn['auc_rule'], 3)})", "Satış"],
            ["<b>ABC-XYZ</b>", "Ciro katkısı ve aylık talep değişkenliği", "A %80, B %95; X &lt; 0,5 ≤ Y &lt; 1,0 ≤ Z; 2020 tamamı; talep ve ciro önceliklendirmesi (stok politikası değil)", "Ürün ve Tedarik"],
            ["<b>Satış tahmini</b>", "Naive, doğrusal trend, üstel düzeltme (Holt, sönümlü)",
             f"Kayıt boşluğu enterpolasyonla doldurulur, pandemi döneminde Hampel filtresi uygulanır; {fc['n_folds']} adımlı kayan "
             f"doğrulamayla seçim (sızıntısız), son 4 hafta ayrı test. Seçilen: {tr_lower(best)} (doğrulama MAPE "
             f"{fmt_pct(fc['table'].loc[best, 'mape'])}, son test {fmt_pct(fc['test'][best])})", "Tahmin"],
            ["<b>Asistan</b>", "Soru çözümleme + hesaplama + yanıt", "Kapsamı soru belirler; sayılar paneldeki hesaplardan gelir, dil modeli yalnızca çözümler ve yazar", "Yönetici Özeti"],
        ], ["left", "left", "left", "left"])
        section_header("Terimler")
        html_table(["Terim", "Anlamı", "Nerede"], [
            ["<b>Müşteri segmenti</b>", "K-ortalamalarla bulunan davranış grubu (ör. Çekirdek Kitabevleri, Uykudaki Müşteriler). 2020 yıl sonuna göre bir kez belirlenir, dönemle değişmez.", "Filtre, Pazarlama"],
            ["<b>RFM segmenti</b>", "Son alım, sıklık ve tutar puanlarından kuralla belirlenen ilişki aşaması (ör. Şampiyonlar, Risk Altında, Kayıp). Seçili dönemin sonuna göre hesaplanır.", "Satış → RFM Segmentleri"],
            ["<b>Hareketsiz müşteri</b>", "Önceki dönemde alım yapıp seçili dönemde yapmayan müşteri. Gözlenen bir durumdur; müşteri sonraki dönemde geri dönebilir.", "Satış → Müşteri Hareketi"],
            ["<b>Kayıp riski</b>", "Modelin, müşterinin sonraki 92 günde alım yapmama olasılığı. Geleceğe dair bir tahmindir.", "Satış → Kayıp Riski"],
        ], ["left", "left", "left"])
    with tabs[5]:
        section_header("Aksiyon kuralları")
        st.caption("Paneldeki her öneri bu kurallardan biriyle üretilir. Model başarısına dayanan tahmin önerileri (ciro hedefi, "
                   "kategori sinyali) yalnızca seçilen model naive referansını geçerse gösterilir; sevkiyat kapasitesi planı her "
                   "durumda üretilir ve hangi yönteme dayandığını belirtir. Yönetici Özeti satış, pazarlama ve tedarikten birer "
                   "öneri gösterir.")
        html_table(["Öneri", "Tetikleyici kural", "Departman", "Dayanak"], [
            ["<b>Yeniden temas</b>", "Önceki dönemde alıp seçili dönemde almayan (hareketsiz) müşteriler", "Satış", "Veri"],
            ["<b>Büyük müşteri teması</b>", "Önceki dönem cirosu en yüksek hareketsiz müşteri, 90 günden uzun süredir alım yoksa", "Satış", "Veri"],
            ["<b>Kayıp riski ataması</b>", "Kayıp olasılığı × 2020 cirosu en yüksek 20 müşteri", "Satış", "Tahmin"],
            ["<b>İkinci sipariş</b>", "İlk alımını seçili dönemde yapan müşteriler", "Satış", "Veri"],
            ["<b>Çapraz satış</b>", "Segmentte kategori alım oranı Çekirdek Kitabevleri'nin yarısından az (uykudaki müşteriler hariç)", "Pazarlama", "Veri"],
            ["<b>İskonto incelemesi</b>", "Ağırlıklı iskontosu %35–45 bandının dışında kalan müşteriler", "Pazarlama", "Veri"],
            ["<b>Yakın takip (AZ)</b>", "ABC-XYZ matrisinin AZ hücresi: ciroya katkısı yüksek, talebi düzensiz ürünler", "Tedarik", "Veri"],
            ["<b>Kapasite</b>", "Bir günün adet payı salı–cuma ortalamasının 1,5 katını aşıyor", "Tedarik", "Veri"],
            ["<b>Sevkiyat kapasitesi planı</b>", "8 haftalık adet tahmini ve son 13 haftanın gün dağılımı; model naive referansını geçemezse referans (naive) tahminle yapılır ve yöntem kartta yazılır", "Tedarik", "Tahmin"],
            ["<b>Sipariş planı / hedef</b>", "Toplam ciro tahmini ve %80 aralığı", "Tedarik, Yönetim", "Tahmin"],
            ["<b>Kategori sinyali</b>", "Tahmin aralığı son 8 hafta ortalamasının tamamen üstünde ya da altında (tedarikte adet, pazarlamada ciro)", "Tedarik, Pazarlama", "Tahmin"],
            ["<b>Model izleme</b>", "Gerçekleşen %80 aralığın dışına çıkarsa model yeniden kurulur", "Veri", "Tahmin"],
            ["<b>Kontrol listesi</b>", "Hesaplamalardan ayrılan kayıtların kaynak sistemde doğrulanması", "Veri", "Veri"],
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
            ["<b>Asistan (Yönetici Özeti)</b>", "Sorudaki dönem; yoksa sayfadaki dönem", "Yalnızca soruda geçerse", "Yalnızca soruda geçerse", "Yalnızca soruda geçerse"],
        ], ["left", "left", "left", "left", "left"])

with side:
    action_cards([
        Action("Veri", f"{fmt_number(n_aside)} kaydı kaynak sistemde doğrula",
               "Kontrol listesindeki kayıtlar (eksik adet, sıfır fiyat, yer tutucu fiyat, bedelsiz sevkiyat) hesaplamalara girmiyor.",
               PAGE_NOTES, "Kontrol listesi", tab="Temizleme ve Kontrol Listesi"),
        Action("Veri", "Faturalara kalem numarası eklenmesini iste",
               f"{fmt_number(dup['silinen_satir'])} tekrar eden satırın çift kayıt mı, ayrı kalem mi olduğu ayırt edilemiyor.",
               PAGE_NOTES, "Silinen tekrarlar", tab="Temizleme ve Kontrol Listesi"),
        Action("Veri", "NetPrice'ın KDV durumunu doğrula", "İskonto ve ciro yorumları bu varsayıma dayanıyor.",
               PAGE_NOTES, "Varsayımlar", tab="Varsayımlar ve Sınırlılıklar"),
    ])

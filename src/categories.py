"""Kategori hiyerarşisi: Ana kategori → Alt kategori (standart) → Orijinal kategori.

Tasarım ilkeleri
- Eşleme açık bir sözlükle yapılır (anahtar kelimeyle toplu birleştirme yok). Her orijinal etiketin
  standart adı ve ana kategorisi aşağıda tek tek yazılıdır; denetim tablosu her değişikliği gösterir.
- Yalnızca gerçekten eşdeğer etiketler birleştirilir (ör. "Masal & Hikaye Kitapları" ve "Masal - Hikaye").
  Polisiye, Fantastik, Romantik gibi farklı türler alt kategori düzeyinde ayrı kalır.
- İngilizce etiketler Türkçeye çevrilir. Bu etiketlerin altındaki ürünler yabancı dilde yayınlar olduğu
  için (ör. "Classics" = İngilizce okuma kitapları) "Yabancı Dilde …" adıyla Dil ve Yabancı Diller altına alınır.
- Ders/sınav kitapları konu adı taşısa da (Fizik, Biyoloji, Edebiyat) Eğitim ve Sınav altına gider:
  örnek başlıklar "Palme 11. Sınıf Fizik Soru Kitabı" gibidir.
- Emin olunamayan eşlemeler "Needs Review" olarak işaretlenir; sessizce değiştirilmez.
- Felsefe, sosyal bilimler, siyaset ve hukuk için 15. ana kategori (Felsefe ve Toplum Bilimleri)
  kullanıcı onayıyla eklendi; bu etiketler önceden "Diğer" altında incelemedeydi.
"""

import re

import pandas as pd

MAIN_CATEGORIES = [
    "Edebiyat ve Kurgu", "Çocuk ve Gençlik", "Aile ve Ebeveynlik", "Eğitim ve Sınav",
    "Kişisel Gelişim ve Psikoloji", "Felsefe ve Toplum Bilimleri", "Tarih ve Coğrafya", "Din ve Maneviyat", "Bilim ve Teknoloji",
    "İş Dünyası ve Ekonomi", "Sanat ve Kültür", "Sağlık ve Yaşam", "Dil ve Yabancı Diller",
    "Hobi ve Eğlence", "Diğer",
]
E, C, A, S, K, FT, T, D, B, I, SA, H, DL, HO, O = MAIN_CATEGORIES

# Orijinal etiket → (standart alt kategori, ana kategori). Sırası: ana kategoriye göre gruplu.
CATEGORY_MAP = {
    # --- Edebiyat ve Kurgu ---
    "Roman/Öykü": ("Roman/Öykü", E), "Türkiye Roman": ("Türkiye Roman", E), "Dünya Roman": ("Dünya Roman", E),
    "Dünya Klasik": ("Dünya Klasik", E), "Türk Klasik": ("Türk Klasik", E), "Polisiye": ("Polisiye", E),
    "Romantik": ("Romantik", E), "Deneme/Yazın": ("Deneme/Yazın", E), "Türk Şiiri": ("Türk Şiiri", E),
    "Dünya Şiiri": ("Dünya Şiiri", E), "Şiir": ("Şiir", E), "Şiir Antolojisi": ("Şiir Antolojisi", E),
    "Korku Gerilim": ("Korku Gerilim", E), "Fantastik": ("Fantastik", E), "Fantasy": ("Fantastik", E),
    "Fantastik/Bilim Kurgu": ("Fantastik/Bilim Kurgu", E), "Bilim Kurgu": ("Bilim Kurgu", E),
    "Türk Öykü": ("Türk Öykü", E), "Dünya Öykü": ("Dünya Öykü", E), "Öykü Antolojisi": ("Öykü Antolojisi", E),
    "Macera": ("Macera", E), "Edebiyat İnceleme": ("Edebiyat İnceleme", E), "Anlatı": ("Anlatı", E),
    "Kurgu": ("Kurgu", E), "Felsefi Romanlar": ("Felsefi Romanlar", E), "Mizah Romanı - Öykü": ("Mizah Romanı - Öykü", E),
    "Çizgi Roman": ("Çizgi Roman", E), "Destan": ("Destan", E), "Dünya Oyunları": ("Dünya Oyunları", E),
    "Türk Oyunları": ("Türk Oyunları", E), "Dünya Erotik": ("Dünya Erotik", E),
    "Biyografi & Oto Biyografi": ("Biyografi ve Otobiyografi", E), "Biography (History)": ("Biyografi ve Otobiyografi", E),
    "Türk Günlük Anı": ("Türk Günlük Anı", E), "Dünya Günlük Anı": ("Dünya Günlük Anı", E),
    "Türk Mektup": ("Türk Mektup", E), "Dünya Mektup": ("Dünya Mektup", E), "Röportaj": ("Röportaj", E),
    "Söyleşi": ("Söyleşi", E), "Edebiyatçılar": ("Edebiyatçılar", E), "Gezi Anlatımı": ("Gezi Anlatımı", E),
    "Fıkra": ("Fıkra", E), "Halk Ozanları": ("Halk Ozanları", E), "Sporcular": ("Sporcular", E),
    "Sanatçılar": ("Sanatçılar", E), "Bilim İnsanları": ("Bilim İnsanları", E), "İş Adamları": ("İş Adamları", E),
    "Gazeteciler": ("Gazeteciler", E), "Din Adamları": ("Din Adamları", E), "Kaşifler": ("Kaşifler", E),
    "Felsefeciler": ("Felsefeciler", E),
    # --- Çocuk ve Gençlik ---
    "Çocuk Öykü/Hikaye": ("Çocuk Öykü/Hikaye", C), "Masal & Hikaye Kitapları": ("Masal ve Hikaye Kitapları", C),
    "Masal - Hikaye": ("Masal ve Hikaye Kitapları", C), "Çocuk Eğitim/Etkinlik": ("Çocuk Eğitim/Etkinlik", C),
    "Eğitim Etkinlik Kitapları": ("Eğitim ve Etkinlik Kitapları", C), "Eğitim/Etkinlik": ("Eğitim ve Etkinlik Kitapları", C),
    "Çocuk Klasik": ("Çocuk Klasik", C), "Çocuk Fantastik/Bilim Kurgu": ("Çocuk Fantastik/Bilim Kurgu", C),
    "Çocuk Bilim": ("Çocuk Bilim", C), "Çocuk Kitapları": ("Çocuk Kitapları", C), "Boyama Kitapları": ("Boyama Kitapları", C),
    "Çıkartma Kitapları": ("Çıkartma Kitapları", C), "Okul Öncesi Kitapları": ("Okul Öncesi Kitapları", C),
    "İslami Çocuk Kitapları": ("İslami Çocuk Kitapları", C), "Çocuk Dil Seviye Kitapları": ("Çocuk Dil Seviye Kitapları", C),
    "Çocuk Türk Klasik": ("Çocuk Türk Klasik", C), "Tübitak Kitapları": ("Tübitak Kitapları", C),
    "Çocuk Çizgi Roman Mizah": ("Çocuk Çizgi Roman Mizah", C), "Sesli Görüntülü Çocuk Kitapları": ("Sesli Görüntülü Çocuk Kitapları", C),
    "Sesli Çocuk Kitapları": ("Sesli Çocuk Kitapları", C), "Sesli Eğitim Kitapları": ("Sesli Eğitim Kitapları", C), "Çocuk Şiiri/Şarkıları": ("Çocuk Şiiri/Şarkıları", C),
    "Eğitici Oyunlar": ("Eğitici Oyunlar", C), "Eğitici Oyuncaklar": ("Eğitici Oyuncaklar", C),
    "Çocuk Puzzleları": ("Çocuk Puzzleları", C), "Çocuk Kutu Oyunları": ("Çocuk Kutu Oyunları", C),
    "6+ Yaş Başvuru Kitapları": ("6+ Yaş Başvuru Kitapları", C), "6+ Yaş Klasik Kitaplar": ("6+ Yaş Klasik Kitaplar", C),
    "6+ Yaş Dil Kitapları": ("6+ Yaş Dil Kitapları", C), "Okul Kitapları": ("Okul Kitapları", C),
    # --- Aile ve Ebeveynlik ---
    "Aile - Çocuk": ("Aile ve Çocuk", A), "Aile Çocuk": ("Aile ve Çocuk", A), "Çocuk Gelişim Kitapları": ("Çocuk Gelişim Kitapları", A),
    "Hamilelik ve Çocuk Sağlığı": ("Hamilelik ve Çocuk Sağlığı", A), "İlk Yaş Gelişim": ("İlk Yaş Gelişim", A),
    "Ergenlik Psikolojisi": ("Ergenlik Psikolojisi", A),
    # --- Eğitim ve Sınav ---
    "Temel Yeterlilik Testi - Alan Yeterlilik Testi (YKS-TYT/AYT)": ("YKS (TYT-AYT)", S),
    "Alan Yeterlilik Testi (YKS-AYT)": ("YKS (AYT)", S), "Temel Yeterlilik Testi (YKS-TYT)": ("YKS (TYT)", S),
    "YKS (Yükseköğretim Kurumları Giriş Sınavı)": ("YKS (Genel)", S), "LGS": ("LGS", S), "KPSS": ("KPSS", S),
    "ALES": ("ALES", S), "DGS": ("DGS", S), "YDS": ("YDS", S), "KPDS": ("KPDS", S), "TOEFL": ("TOEFL", S),
    "SPK/SPF": ("SPK/SPF", S), "İş Sağlığı ve Güvenliği Sınavı": ("İş Sağlığı ve Güvenliği Sınavı", S),
    "Diğer Sınav Kitapları": ("Diğer Sınav Kitapları", S), "Tüm Dersler": ("Tüm Dersler", S),
    "Matematik": ("Matematik", S), "Fizik": ("Fizik", S), "Kimya": ("Kimya", S), "Biyoloji": ("Biyoloji", S),
    "Türkçe": ("Türkçe", S), "Sosyal Bilgiler": ("Sosyal Bilgiler", S), "Fen ve Teknoloji": ("Fen ve Teknoloji", S),
    "Edebiyat": ("Türk Dili ve Edebiyatı (Ders)", S), "Dil ve Anlatım": ("Dil ve Anlatım", S),
    "Din Kültürü ve Ahlak Bilgisi": ("Din Kültürü ve Ahlak Bilgisi", S),
    "T.C İnkılap Tarihi ve Atatürkçülük": ("T.C. İnkılap Tarihi ve Atatürkçülük", S),
    "Teknik Ders Kitapları": ("Teknik Ders Kitapları", S), "Öğretmenlik": ("Öğretmenlik", S),
    "Eğitim": ("Eğitim", S), "Kolejler": ("Kolejler", S),
    # --- Kişisel Gelişim ve Psikoloji ---
    "Kişisel Gelişim": ("Kişisel Gelişim", K), "Self Help": ("Kişisel Gelişim", K),
    "Psikoloji Bilimi": ("Psikoloji", K), "Psikoloji": ("Psikoloji", K), "Kadın Erkek İlişkisi": ("Kadın Erkek İlişkisi", K),
    "Bilgelik": ("Bilgelik", K), "Mind and Spirit": ("Zihin ve Ruh", K), "Ruh Sağlığı": ("Ruh Sağlığı", K),
    "Kadın": ("Kadın", K),  # örnek başlıklar: "Kurtlarla Koşan Kadınlar", "Kadın Olmayı Hatırlamak"
    # --- Felsefe ve Toplum Bilimleri (kullanıcı onayıyla eklenen 15. ana kategori) ---
    "Felsefe Bilimi": ("Felsefe", FT), "Felsefe": ("Felsefe", FT), "Felsefe-Sosyoloji": ("Felsefe-Sosyoloji", FT),
    "Felsefi Süreli Yayınlar": ("Felsefi Süreli Yayınlar", FT), "Sosyoloji": ("Sosyoloji", FT),
    "Antropoloji": ("Antropoloji", FT), "Etnoloji": ("Etnoloji", FT), "Sosyal Bilimler": ("Sosyal Bilimler", FT),
    "Medya": ("Medya", FT), "İletişim": ("İletişim", FT),  # örnek başlıklar: iletişim kuramları, gazetecilik
    "Politika": ("Politika", FT), "Politics and Current Affairs": ("Politika", FT),
    "Türkiye Politika": ("Türkiye Politika", FT), "Dünya Politika": ("Dünya Politika", FT),
    "Uluslararası ilişkiler": ("Uluslararası İlişkiler", FT), "Avrupa Birliği - Türkiye": ("Avrupa Birliği - Türkiye", FT),
    "Hukuk": ("Hukuk", FT), "Sivil Toplum Örgütleri": ("Sivil Toplum Örgütleri", FT), "Organize Suç": ("Organize Suç", FT),
    # --- Tarih ve Coğrafya ---
    "Dünya Tarihi": ("Dünya Tarihi", T), "Osmanlı Tarihi": ("Osmanlı Tarihi", T), "Türk Tarihi": ("Türk Tarihi", T),
    "Cumhuriyet Tarihi": ("Cumhuriyet Tarihi", T), "Tarih": ("Tarih", T), "Kuramsal Tarih": ("Kuramsal Tarih", T),
    "Tarih Prestij": ("Tarih Prestij", T), "History & Military": ("Askeri Tarih", T), "History and War": ("Askeri Tarih", T),
    "Atatürk": ("Atatürk", T), "Atatürk Prestij": ("Atatürk Prestij", T), "Tarihi Kişiler": ("Tarihi Kişiler", T),
    "Devlet Adamları": ("Devlet Adamları", T), "Türkiye": ("Türkiye", T), "Türkiye Prestij": ("Türkiye Prestij", T),
    "Ermeni Meselesi": ("Ermeni Meselesi", T), "Arkeoloji": ("Arkeoloji", T), "Coğrafya": ("Coğrafya", T),
    "Atlas": ("Atlas", T), "Harita": ("Harita", T), "Ülkeler Kentler": ("Ülkeler Kentler", T),
    "İstanbul Kitapları": ("İstanbul Kitapları", T), "İstanbul Prestij": ("İstanbul Prestij", T),
    "Gezi İstanbul": ("Gezi İstanbul", T), "Gezi": ("Gezi", T), "Rehber": ("Gezi Rehberi", T), "Turizm": ("Turizm", T),
    # --- Din ve Maneviyat ---
    "Tasavvuf": ("Tasavvuf", D), "İslamiyet": ("İslamiyet", D), "İslami": ("İslami", D), "İslam Prestij": ("İslam Prestij", D),
    "İslam ve Din Bilimleri": ("İslam ve Din Bilimleri", D), "Din": ("Din", D), "Alevilik - Bektaşilik": ("Alevilik - Bektaşilik", D),
    "Hristiyanlık": ("Hristiyanlık", D), "Musevilik": ("Musevilik", D), "Budizm": ("Budizm", D), "Diğer İnançlar": ("Diğer İnançlar", D),
    "Religion and Myths/Spirituality": ("Din, Mitoloji ve Maneviyat", D), "Parapsikoloji": ("Parapsikoloji", D),
    "Astroloji-Fal-Büyü": ("Astroloji-Fal-Büyü", D), "Rüya Tabirleri": ("Rüya Tabirleri", D), "Kehanet": ("Kehanet", D),
    "Yoga Meditasyon": ("Yoga Meditasyon", D),
    # --- Bilim ve Teknoloji ---
    "Popüler Bilim": ("Popüler Bilim", B), "Bilim": ("Bilim", B), "Bilim Tarihi ve Felsefesi": ("Bilim Tarihi ve Felsefesi", B),
    "Astronomi": ("Astronomi", B), "Bilgisayar": ("Bilgisayar", B), "Bilişim Teknolojileri": ("Bilişim Teknolojileri", B),
    "Mühendislik": ("Mühendislik", B), "Ekoloji/Çevre Bilim": ("Ekoloji/Çevre Bilim", B), "Botanik": ("Botanik", B),
    "Zooloji": ("Zooloji", B), "Jeoloji": ("Jeoloji", B), "Biyoloji/Genetik": ("Biyoloji/Genetik", B),
    "Anatomi": ("Anatomi", B), "İstatistik": ("İstatistik", B), "Keşifler": ("Keşifler", B), "Doğa Prestij": ("Doğa Prestij", B),
    # --- İş Dünyası ve Ekonomi ---
    "Yönetim / İş Geliştirme / Kalite": ("Yönetim / İş Geliştirme / Kalite", I), "Ekonomi": ("Ekonomi", I),
    "İktisat/Ekonomi": ("Ekonomi", I), "Finans": ("Finans", I), "Borsa": ("Borsa", I),
    "Satış - Pazarlama/Halkla İlişkiler": ("Satış - Pazarlama/Halkla İlişkiler", I), "İnsan Kaynakları": ("İnsan Kaynakları", I),
    "İşletme": ("İşletme", I), "Dış Ticaret": ("Dış Ticaret", I), "Maliye/Muhasebe": ("Maliye/Muhasebe", I),
    "Kamu": ("Kamu Maliyesi", I), "Business and Economics": ("İş ve Ekonomi", I),
    # --- Sanat ve Kültür ---
    "Müzik": ("Müzik", SA), "Tiyatro": ("Tiyatro", SA), "Tiyatro Tekniği": ("Tiyatro Tekniği", SA), "Sinema": ("Sinema", SA),
    "Senaryo": ("Senaryo", SA), "Sanat Tarihi ve Kuramı": ("Sanat Tarihi ve Kuramı", SA),
    "Resim-Plastik Sanatlar": ("Resim-Plastik Sanatlar", SA), "Resim Tekniği": ("Resim Tekniği", SA), "Mimari": ("Mimari", SA),
    "Fotoğraf - Grafik Sanatı": ("Fotoğraf - Grafik Sanatı", SA), "Fotoğraf": ("Fotoğraf", SA),
    "Fotograf Prestij": ("Fotoğraf Prestij", SA), "Sanat Prestij": ("Sanat Prestij", SA), "Diğer Sanatlar": ("Diğer Sanatlar", SA),
    "Türk Osmanlı Sanatı": ("Türk Osmanlı Sanatı", SA), "Karikatür": ("Karikatür", SA), "Moda": ("Moda", SA),
    "Mitoloji Efsane": ("Mitoloji Efsane", SA),
    # --- Sağlık ve Yaşam ---
    "Beden Sağlığı": ("Beden Sağlığı", H), "Beslenme Diyet": ("Beslenme Diyet", H), "Yemek Kitapları": ("Yemek Kitapları", H),
    "Food": ("Yemek Kitapları", H), "Gastronomi": ("Gastronomi", H), "İçkiler ve Kokteyller": ("İçkiler ve Kokteyller", H),
    "Geleneksel Sağlık Yöntemleri": ("Geleneksel Sağlık Yöntemleri", H), "Kadın Sağlığı": ("Kadın Sağlığı", H),
    "Tıp": ("Tıp", H), "Cinsellik": ("Cinsellik", H), "Uyuşturucu ve Alkolizm": ("Uyuşturucu ve Alkolizm", H),
    "Health/Fitness/Psychology": ("Sağlık, Fitness ve Psikoloji", H),
    # --- Dil ve Yabancı Diller ---
    "Sözlük": ("Sözlük", DL), "Dictionary": ("Sözlük", DL), "Dilbilimi/Etimoloji": ("Dilbilimi/Etimoloji", DL),
    "Graded Readers": ("Kademeli Okuma Kitapları", DL), "Phrase Book and Language": ("Konuşma Kılavuzu ve Dil", DL),
    "Grammar and Vocabulary": ("Dil Bilgisi ve Kelime", DL), "Exam Books": ("Yabancı Dil Sınav Kitapları", DL),
    "Classics": ("Yabancı Dilde Klasikler", DL), "Literature": ("Yabancı Dilde Edebiyat", DL),
    "Mystery/Crime/Thriller": ("Yabancı Dilde Polisiye ve Gerilim", DL),
    "Children": ("Yabancı Dilde Çocuk Kitapları", DL), "Children Interest": ("Yabancı Dilde Çocuk Kitapları", DL),
    "Storybook": ("Yabancı Dilde Hikaye Kitapları", DL), "Characters": ("Yabancı Dilde Karakter Kitapları", DL),
    "Preschool": ("Yabancı Dilde Okul Öncesi", DL), "Foreign Language Prestij": ("Yabancı Dil Prestij", DL),
    "Yabancı Dil": ("Yabancı Dil", DL), "Other Languages": ("Diğer Diller", DL), "Russian": ("Rusça", DL),
    "Spanish": ("İspanyolca", DL), "Italian": ("İtalyanca", DL), "German": ("Almanca", DL), "Arabic": ("Arapça", DL),
    "Kürtçe": ("Kürtçe", DL), "Osmanlıca": ("Osmanlıca", DL), "Other (Reference)": ("Diğer Başvuru Kitapları", DL),
    # --- Hobi ve Eğlence ---
    "Bulmaca": ("Bulmaca", HO), "1000 Parça Puzzle": ("1000 Parça Puzzle", HO), "500 Parça Puzzle": ("500 Parça Puzzle", HO),
    "1500 Parça Puzzle": ("1500 Parça Puzzle", HO), "2000 Parça Puzzle": ("2000 Parça Puzzle", HO),
    "3000+ Parça Puzzle": ("3000+ Parça Puzzle", HO), "75-300 Parça Puzzle": ("75-300 Parça Puzzle", HO),
    "Puzzle Aksesuarları": ("Puzzle Aksesuarları", HO), "Oyun Kitapları/Oyun": ("Oyun Kitapları/Oyun", HO),
    "Hobi Oyuncakları": ("Hobi Oyuncakları", HO), "Genel İlgi": ("Genel İlgi", HO), "Spor": ("Spor", HO),
    "El Sanatları": ("El Sanatları", HO), "Hayvan Bakımı": ("Hayvan Bakımı", HO), "Bahçe Bakımı/Çiçek Sanatı": ("Bahçe Bakımı/Çiçek Sanatı", HO),
    "Avcılık": ("Avcılık", HO), "Outdoor - Survival": ("Doğa ve Hayatta Kalma", HO),
    "Eğlenceli Kitaplar/Hediyelik Kitaplar": ("Eğlenceli Kitaplar/Hediyelik Kitaplar", HO),
    # --- Diğer (bilinen gruplara gerçekten uymayanlar: kırtasiye, süreli yayın, karışık prestij setleri) ---
    "Kap Kağıtları": ("Kap Kağıtları", O), "Not Defterleri": ("Not Defterleri", O), "Butik Defterler": ("Butik Defterler", O),
    "Resim Defterleri": ("Resim Defterleri", O), "Hatıra ve Şiir Defterleri": ("Hatıra ve Şiir Defterleri", O),
    "Organizer ve Ajandalar": ("Organizer ve Ajandalar", O), "Takvimler": ("Takvimler", O), "Masa Setleri": ("Masa Setleri", O),
    "Keçe Uçlu Kalemler": ("Keçe Uçlu Kalemler", O), "Kart Zarf ve Mektupluklar": ("Kart Zarf ve Mektupluklar", O),
    "Aylık Dergi": ("Aylık Dergi", O), "Almanak": ("Almanak", O),
    "Ansiklopedi": ("Ansiklopedi", O), "Diğer Prestij": ("Diğer Prestij", O),
}

TRANSLATED = {"Fantasy", "Biography (History)", "Self Help", "Mind and Spirit", "History & Military", "History and War",
              "Religion and Myths/Spirituality", "Business and Economics", "Food", "Health/Fitness/Psychology",
              "Dictionary", "Graded Readers", "Phrase Book and Language", "Grammar and Vocabulary", "Exam Books",
              "Classics", "Literature", "Mystery/Crime/Thriller", "Children", "Children Interest", "Storybook",
              "Characters", "Preschool", "Foreign Language Prestij", "Other Languages", "Russian", "Spanish",
              "Italian", "German", "Arabic", "Other (Reference)", "Outdoor - Survival", "Politics and Current Affairs"}

# Ana kategorisi tartışmalı olan eşlemeler: kullanıcı onayına kadar işaretli kalır
NEEDS_REVIEW = {
    "Eğitim": "Başlıklar karışık (yazılım, İngilizce test, masal)",
    "Kolejler": "Tek ürün; etiketin anlamı belirsiz",
    "Okul Kitapları": "Başlıklar karışık; çocuk kitabı ağırlıklı",
    "Bilgelik": "Kişisel gelişim ile maneviyat arasında",
    "Other (Reference)": "Tek ürün (Osmanlıca); başvuru kitabı",
    "Diğer Prestij": "Başlıklar karışık (sözlük, bitkiler, yemek)",
}

# Onaylanmış ürün–kategori eşlemeleri (Öncelik 1)
APPROVED_PRODUCT_MAP = {"9786057988423": "Çocuk Kitapları"}  # Baybarsın Mısır Macerası

# Sözlükte olmayan yeni etiketler için yedek kurallar: en özelden en genele sıralı.
# Bu kurallarla yapılan her eşleme "Needs Review" olarak işaretlenir.
FALLBACK_RULES = [
    (r"\bçocuk\b|\bmasal\b|okul öncesi|\bboyama\b", C), (r"\b(yks|tyt|ayt|lgs|kpss|ales|dgs|sınav)\b", S),
    (r"\bpuzzle\b|\bbulmaca\b", HO), (r"\bsözlük\b|\bdictionary\b|\bgrammar\b", DL),
    (r"\broman\b|\böykü\b|\bşiir\b|\bpolisiye\b", E), (r"\btarih\b|\bhistory\b", T), (r"\bislam\b|\bdin\b", D),
]

SUBCATEGORY_TO_MAIN = {std: main for std, main in CATEGORY_MAP.values()}


def _key(text: str) -> str:
    """Karşılaştırma anahtarı: boşlukları sadeleştirir, Türkçe kurallarıyla küçük harfe çevirir."""
    t = re.sub(r"\s+", " ", str(text)).strip()
    return t.replace("I", "ı").replace("İ", "i").lower()


_LOOKUP = {_key(k): k for k in CATEGORY_MAP}


def standardize(original) -> tuple[str | None, str | None, str]:
    """Orijinal etiket → (standart alt kategori, ana kategori, eşleme durumu)."""
    if original is None or (isinstance(original, float) and pd.isna(original)) or str(original).strip() == "":
        return None, None, "Missing"
    clean = re.sub(r"\s+", " ", str(original)).strip()
    known = _LOOKUP.get(_key(clean))
    if known is None:
        for pattern, main in FALLBACK_RULES:
            if re.search(pattern, _key(clean)):
                return clean, main, "Needs Review"
        return clean, O, "Needs Review"
    std, main = CATEGORY_MAP[known]
    if known in NEEDS_REVIEW:
        status = "Needs Review"
    elif known in TRANSLATED:
        status = "Translated"
    elif sum(1 for v in CATEGORY_MAP.values() if v[0] == std) > 1:
        status = "Merged"
    elif std != known or clean != str(original):
        status = "Normalized"
    else:
        status = "Unchanged"
    return std, main, status


def main_category(subcategory: str | None) -> str | None:
    """Standart alt kategoriden ana kategori; bilinmeyen alt kategori için None."""
    return SUBCATEGORY_TO_MAIN.get(subcategory) if subcategory else None


def _norm_desc(text) -> str:
    return re.sub(r"[^\w]+", " ", _key(text)).strip()


def apply_hierarchy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Kategori kolonlarını ekler; denetim tablosunu ve kalite raporunu döndürür.

    Eklenen kolonlar: Category_Original, Category_Standardized, Main_Category,
    Category_Assignment_Method, Category_Status.
    """
    df = df.copy()
    df["Category_Original"] = df["Category"].where(df["Category"].notna(), None)
    mapped = {c: standardize(c) for c in df["Category_Original"].dropna().unique()}
    df["Category_Standardized"] = df["Category_Original"].map(lambda c: mapped[c][0] if c in mapped else None)
    df["Main_Category"] = df["Category_Original"].map(lambda c: mapped[c][1] if c in mapped else None)
    df["Category_Assignment_Method"] = df["Category_Original"].map(lambda c: "Existing Category" if c in mapped else None)

    missing = df["Category_Standardized"].isna()
    missing_before = int(missing.sum())
    known = df[~missing]
    # Öncelik 2 ve 3 için tek anlamlı eşlemeler (birden fazla kategori varsa kullanılmaz)
    by_sku = known.groupby("StockCode")["Category_Standardized"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    desc_key = known["Description"].map(_norm_desc)
    by_desc = known.groupby(desc_key)["Category_Standardized"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)

    for idx in df.index[missing]:
        sku, desc = str(df.at[idx, "StockCode"]), _norm_desc(df.at[idx, "Description"])
        if sku in APPROVED_PRODUCT_MAP:
            cat, method = APPROVED_PRODUCT_MAP[sku], "Approved Product Mapping"
        elif pd.notna(by_sku.get(sku)):
            cat, method = by_sku[sku], "StockCode Matching"
        elif pd.notna(by_desc.get(desc)):
            cat, method = by_desc[desc], "Description Matching"
        else:
            cat, method = None, "Manual Review"
        df.at[idx, "Category_Standardized"] = cat
        df.at[idx, "Main_Category"] = main_category(cat) if cat else None
        df.at[idx, "Category_Assignment_Method"] = method

    status = df["Category_Original"].map(lambda c: mapped[c][2] if c in mapped else None)
    df["Category_Status"] = "Assigned"
    df.loc[status.eq("Needs Review") | df["Category_Assignment_Method"].eq("Manual Review"), "Category_Status"] = "Needs Review"
    df["Category_Standardized"] = df["Category_Standardized"].fillna("İnceleme bekliyor")
    df["Main_Category"] = df["Main_Category"].fillna(O)

    # --- Denetim tablosu ---
    audit = (df.groupby(df["Category_Original"].fillna("(boş)"), dropna=False)
             .agg(Category_Standardized=("Category_Standardized", "first"), Main_Category=("Main_Category", "first"),
                  Records=("StockCode", "size"), Unique_Products=("StockCode", "nunique"))
             .rename_axis("Category_Original").reset_index())
    audit["Mapping_Status"] = audit["Category_Original"].map(lambda c: mapped[c][2] if c in mapped else "Missing")
    audit["Review_Note"] = audit["Category_Original"].map(lambda c: NEEDS_REVIEW.get(c, ""))
    audit = audit.sort_values("Records", ascending=False).reset_index(drop=True)

    # --- Kalite raporu ---
    std_counts = audit[audit["Mapping_Status"] != "Missing"].groupby("Category_Standardized").size()
    main_dist = df.groupby("Main_Category").agg(records=("StockCode", "size"), products=("StockCode", "nunique"))
    report = {
        "original_categories": int(df["Category_Original"].nunique()),
        "standardized_categories": int(df.loc[df["Category_Status"].ne("Needs Review") | df["Category_Original"].notna(),
                                              "Category_Standardized"].nunique()),
        "missing_before": missing_before,
        "classified_missing": int((missing & df["Category_Assignment_Method"].ne("Manual Review")).sum()),
        "unresolved": int(df["Category_Assignment_Method"].eq("Manual Review").sum()),
        "merged_labels": int(sum(n - 1 for n in std_counts if n > 1)),
        "mapping_status_labels": audit["Mapping_Status"].value_counts().to_dict(),
        "needs_review_records": int(df["Category_Status"].eq("Needs Review").sum()),
        "by_method": df["Category_Assignment_Method"].value_counts().to_dict(),
        "main_distribution": {m: {"records": int(r.records), "products": int(r.products)}
                              for m, r in main_dist.reindex(MAIN_CATEGORIES).dropna().iterrows()},
    }
    return df, audit, report

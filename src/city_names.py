"""Ham veride büyük harf ve kısmen ASCII yazılmış il adlarının resmi yazımı.

Ham veride 'ISTANBUL' gibi İ yerine I kullanıldığından, Python'un .title()
fonksiyonu doğru sonuç vermez ('Istanbul'). Ayrıca iki ilin eski adı geçiyor:
IÇEL (2002'den beri Mersin) ve AFYON (Afyonkarahisar).
"""

CITY_NAMES = {
    "ADANA": "Adana", "ADIYAMAN": "Adıyaman", "AFYON": "Afyonkarahisar",
    "AGRI": "Ağrı", "AKSARAY": "Aksaray", "AMASYA": "Amasya",
    "ANKARA": "Ankara", "ANTALYA": "Antalya", "ARDAHAN": "Ardahan",
    "ARTVIN": "Artvin", "AYDIN": "Aydın", "BALIKESIR": "Balıkesir",
    "BARTIN": "Bartın", "BATMAN": "Batman", "BAYBURT": "Bayburt",
    "BILECIK": "Bilecik", "BINGÖL": "Bingöl", "BITLIS": "Bitlis",
    "BOLU": "Bolu", "BURDUR": "Burdur", "BURSA": "Bursa",
    "DENIZLI": "Denizli", "DIYARBAKIR": "Diyarbakır", "DÜZCE": "Düzce",
    "EDIRNE": "Edirne", "ELAZIG": "Elazığ", "ERZINCAN": "Erzincan",
    "ERZURUM": "Erzurum", "ESKISEHIR": "Eskişehir", "GAZIANTEP": "Gaziantep",
    "GIRESUN": "Giresun", "GÜMÜSHANE": "Gümüşhane", "HATAY": "Hatay",
    "IGDIR": "Iğdır", "ISPARTA": "Isparta", "ISTANBUL": "İstanbul",
    "IZMIR": "İzmir", "IÇEL": "Mersin", "K.MARAS": "Kahramanmaraş",
    "KARABÜK": "Karabük", "KARAMAN": "Karaman", "KARS": "Kars",
    "KASTAMONU": "Kastamonu", "KAYSERI": "Kayseri", "KIRKLARELI": "Kırklareli",
    "KIRSEHIR": "Kırşehir", "KOCAELI": "Kocaeli", "KONYA": "Konya",
    "KÜTAHYA": "Kütahya", "MALATYA": "Malatya", "MANISA": "Manisa",
    "MARDIN": "Mardin", "MUGLA": "Muğla", "MUS": "Muş",
    "NEVSEHIR": "Nevşehir", "NIGDE": "Niğde", "ORDU": "Ordu",
    "OSMANIYE": "Osmaniye", "RIZE": "Rize", "SAKARYA": "Sakarya",
    "SAMSUN": "Samsun", "SANLIURFA": "Şanlıurfa", "SIIRT": "Siirt",
    "SINOP": "Sinop", "SIVAS": "Sivas", "TEKIRDAG": "Tekirdağ",
    "TOKAT": "Tokat", "TRABZON": "Trabzon", "TUNCELI": "Tunceli",
    "USAK": "Uşak", "VAN": "Van", "YALOVA": "Yalova",
    "YOZGAT": "Yozgat", "ZONGULDAK": "Zonguldak", "ÇANAKKALE": "Çanakkale",
    "ÇANKIRI": "Çankırı", "ÇORUM": "Çorum",
}

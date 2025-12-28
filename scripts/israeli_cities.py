"""Comprehensive list of Israeli cities and municipalities for GTFS parsing.

This module contains mappings of Hebrew city names to English names,
including all major cities, towns, and municipalities in Israel.
"""

# Comprehensive city mappings (Hebrew to English)
# Includes all major cities, regional councils, and municipalities
ISRAELI_CITIES = {
    # Major Cities (>100,000 population)
    "תל אביב": "Tel Aviv",
    "תל-אביב": "Tel Aviv",
    "תל אביב יפו": "Tel Aviv",
    "ירושלים": "Jerusalem",
    "חיפה": "Haifa",
    "ראשון לציון": "Rishon LeZion",
    "פתח תקווה": "Petah Tikva",
    "פתח-תקווה": "Petah Tikva",
    "אשדוד": "Ashdod",
    "נתניה": "Netanya",
    "באר שבע": "Be'er Sheva",
    "באר-שבע": "Be'er Sheva",
    "בני ברק": "Bnei Brak",
    "בני-ברק": "Bnei Brak",
    "חולון": "Holon",
    "רמת גן": "Ramat Gan",
    "רמת-גן": "Ramat Gan",
    "אשקלון": "Ashkelon",
    "רחובות": "Rehovot",
    "בת ים": "Bat Yam",
    "בת-ים": "Bat Yam",

    # Medium Cities (50,000-100,000)
    "הרצליה": "Herzliya",
    "כפר סבא": "Kfar Saba",
    "כפר-סבא": "Kfar Saba",
    "חדרה": "Hadera",
    "מודיעין": "Modi'in",
    "מודיעין מכבים רעות": "Modi'in",
    "נצרת": "Nazareth",
    "לוד": "Lod",
    "רמלה": "Ramla",
    "רעננה": "Ra'anana",
    "רעננה": "Ra'anana",
    "קריית אתא": "Kiryat Ata",
    "קריית גת": "Kiryat Gat",
    "קריית מוצקין": "Kiryat Motzkin",
    "קריית ביאליק": "Kiryat Bialik",
    "קריית ים": "Kiryat Yam",
    "קריית שמונה": "Kiryat Shmona",
    "נהריה": "Nahariya",
    "טבריה": "Tiberias",
    "עכו": "Acre",
    "אילת": "Eilat",
    "טירת כרמל": "Tirat Carmel",
    "עפולה": "Afula",
    "רהט": "Rahat",
    "גבעתיים": "Givatayim",
    "קריית אונו": "Kiryat Ono",
    "הוד השרון": "Hod HaSharon",
    "הוד-השרון": "Hod HaSharon",
    "רמת השרון": "Ramat HaSharon",
    "רמת-השרון": "Ramat HaSharon",

    # Smaller Cities and Towns
    "אור יהודה": "Or Yehuda",
    "אור-יהודה": "Or Yehuda",
    "אור עקיבא": "Or Akiva",
    "אופקים": "Ofakim",
    "אריאל": "Ariel",
    "אשר": "Asher",
    "באקה אל-גרבייה": "Baqa al-Gharbiyye",
    "בית שאן": "Beit She'an",
    "בית-שאן": "Beit She'an",
    "בית שמש": "Beit Shemesh",
    "ביתר עילית": "Beitar Illit",
    "בסמה": "Basma",
    "בנימינה": "Binyamina",
    "גדרה": "Gedera",
    "דימונה": "Dimona",
    "הוד-השרון": "Hod HaSharon",
    "זכרון יעקב": "Zichron Ya'akov",
    "חדרה": "Hadera",
    "חולון": "Holon",
    "חורה": "Hura",
    "חצור הגלילית": "Hatzor HaGlilit",
    "טייבה": "Tayibe",
    "טירה": "Tira",
    "טמרה": "Tamra",
    "יבנה": "Yavne",
    "יהוד": "Yehud",
    "יהוד מונוסון": "Yehud-Monosson",
    "יקנעם": "Yokneam",
    "ירוחם": "Yeruham",
    "כפר יונה": "Kfar Yona",
    "כפר קאסם": "Kfar Qasim",
    "כרמיאל": "Carmiel",
    "כרמי גת": "Kiryat Gat",
    "מגדל העמק": "Migdal HaEmek",
    "מג'ד אל-כרום": "Majd al-Krum",
    "מעלה אדומים": "Ma'ale Adumim",
    "מעלות תרשיחא": "Ma'alot-Tarshiha",
    "מצפה רמון": "Mitzpe Ramon",
    "נס ציונה": "Ness Ziona",
    "נשר": "Nesher",
    "נתיבות": "Netivot",
    "סח'נין": "Sakhnin",
    "עראבה": "Arraba",
    "ערד": "Arad",
    "פרדס חנה": "Pardes Hanna",
    "פרדס-חנה": "Pardes Hanna",
    "צפת": "Safed",
    "קלנסווה": "Qalansawe",
    "קצרין": "Katzrin",
    "רהט": "Rahat",
    "רמת גן": "Ramat Gan",
    "רעננה": "Ra'anana",
    "שדרות": "Sderot",
    "שפרעם": "Shefa-'Amr",
    "תל שבע": "Tel Sheva",

    # Tel Aviv neighborhoods (often appear as separate)
    "יפו": "Tel Aviv - Jaffa",
    "רמת אביב": "Tel Aviv - Ramat Aviv",
    "גבעת שמואל": "Givat Shmuel",
    "קריית מלאכי": "Kiryat Malakhi",

    # Jerusalem areas
    "בית וגן": "Jerusalem - Beit Vagan",
    "גבעת שאול": "Jerusalem - Givat Shaul",
    "תלפיות": "Jerusalem - Talpiot",

    # Gush Dan (Greater Tel Aviv)
    "אזור": "Azor",
    "גן יבנה": "Gan Yavne",
}

# English city name variants
ENGLISH_VARIANTS = {
    "Tel Aviv": "Tel Aviv",
    "Jerusalem": "Jerusalem",
    "Haifa": "Haifa",
    "Beer Sheva": "Be'er Sheva",
    "Beersheba": "Be'er Sheva",
    "Ashdod": "Ashdod",
    "Netanya": "Netanya",
    "Bnei Brak": "Bnei Brak",
    "Holon": "Holon",
    "Ramat Gan": "Ramat Gan",
    "Petah Tikva": "Petah Tikva",
    "Petach Tikva": "Petah Tikva",
    "Rishon LeZion": "Rishon LeZion",
    "Rishon Lezion": "Rishon LeZion",
    "Ashkelon": "Ashkelon",
    "Rehovot": "Rehovot",
    "Bat Yam": "Bat Yam",
    "Herzliya": "Herzliya",
    "Kfar Saba": "Kfar Saba",
    "Hadera": "Hadera",
    "Modiin": "Modi'in",
    "Nazareth": "Nazareth",
    "Lod": "Lod",
    "Ramla": "Ramla",
    "Raanana": "Ra'anana",
    "Nahariya": "Nahariya",
    "Tiberias": "Tiberias",
    "Acre": "Acre",
    "Akko": "Acre",
    "Eilat": "Eilat",
    "Afula": "Afula",
}

def get_all_city_mappings():
    """Get combined dictionary of all city name mappings."""
    combined = {}
    combined.update(ISRAELI_CITIES)
    combined.update(ENGLISH_VARIANTS)
    return combined


def get_hebrew_name(english_city: str) -> str:
    """Get Hebrew name for an English city name.

    Args:
        english_city: English city name (e.g., "Tel Aviv")

    Returns:
        Hebrew city name, or empty string if not found
    """
    # Search in ISRAELI_CITIES for the Hebrew name
    for he_city, en_city in ISRAELI_CITIES.items():
        if en_city == english_city:
            return he_city

    # Not found
    return ""

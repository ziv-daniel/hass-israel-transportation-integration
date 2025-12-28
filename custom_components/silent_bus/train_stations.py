"""Major Israeli Railways train stations for dropdown selection.

This module contains a list of major train stations in Israel for use in
the train configuration dropdown. Station IDs are from Israeli Railways.

Source: https://www.rail.co.il
"""

# Major Israeli Railways train stations
# Format: Station ID → (Hebrew Name, English Name)
TRAIN_STATIONS = {
    # Tel Aviv District
    "3600": ("תל אביב - סבידור מרכז", "Tel Aviv - Savidor Center"),
    "3700": ("תל אביב - אוניברסיטה", "Tel Aviv - University"),
    "4600": ("תל אביב - השלום", "Tel Aviv - HaShalom"),
    "4900": ("תל אביב - הגנה", "Tel Aviv - HaHagana"),

    # Central District
    "3500": ("בני ברק", "Bnei Brak"),
    "2800": ("פתח תקווה - קריית אריה", "Petah Tikva - Kiryat Aryeh"),
    "2820": ("פתח תקווה - סגולה", "Petah Tikva - Segula"),
    "9100": ("ראש העין צפון", "Rosh HaAyin North"),
    "9200": ("ראש העין מערב", "Rosh HaAyin West"),
    "4170": ("רחובות", "Rehovot"),
    "4250": ("רחובות מזרח/משעול התקווה", "Rehovot East/Tikva"),
    "4660": ("רמלה", "Ramla"),
    "5150": ("לוד", "Lod"),
    "5300": ("לוד גני אביב", "Lod Ganei Aviv"),
    "4800": ("בית שמש", "Beit Shemesh"),
    "5010": ("מודיעין מרכז", "Modi'in Center"),
    "5000": ("מודיעין מכבים רעות", "Modi'in Makabim Reut"),
    "680": ("כפר חב\"ד", "Kfar Chabad"),

    # Jerusalem
    "6500": ("ירושלים - יצחק נבון", "Jerusalem - Yitzhak Navon"),
    "6300": ("ירושלים - מלחה", "Jerusalem - Malha"),

    # Coastal Plain
    "8550": ("בת ים - יוספטל", "Bat Yam - Yoseftal"),
    "8600": ("בת ים - קוממיות", "Bat Yam - Komemiyut"),
    "8700": ("חולון - וולפסון", "Holon - Wolfson"),
    "8800": ("חולון סבידור", "Holon Savidor"),
    "9000": ("מושב בצרה", "Moshav Bazra"),
    "1220": ("כפר סבא - נורדאו", "Kfar Saba - Nordau"),
    "1240": ("רעננה מערב", "Ra'anana West"),
    "1260": ("רעננה דרום", "Ra'anana South"),
    "1280": ("הוד השרון - סוקולוב", "Hod HaSharon - Sokolov"),
    "2500": ("נתניה", "Netanya"),
    "2100": ("נתניה - ספיר", "Netanya - Sapir"),
    "1300": ("הרצליה", "Herzliya"),
    "2940": ("בית יהושע", "Beit Yehoshua"),
    "3310": ("נתיבות קיסריה", "Caesarea Pardes Hanna"),
    "2760": ("בניימינה", "Binyamina"),
    # "2820": ("עתלית", "Atlit"),  # TODO: Find correct station ID (conflicts with Petah Tikva Segula)

    # Haifa
    "2200": ("חדרה - מערב", "Hadera - West"),
    "2300": ("חיפה - בת גלים", "Haifa - Bat Galim"),
    # "2500": ("חיפה - מרכז השמונה", "Haifa - Merkaz HaShmona"),  # TODO: Find correct ID (conflicts with Netanya)
    # "2800": ("חיפה - חוף הכרמל", "Haifa - Hof HaCarmel"),  # TODO: Find correct ID (conflicts with Petah Tikva)
    "700": ("קריית מוצקין", "Kiryat Motzkin"),
    "1500": ("קריית חיים", "Kiryat Haim"),
    "1820": ("לב המפרץ", "Lev HaMifratz"),
    "4650": ("עכו", "Acre"),
    "4690": ("נהריה", "Nahariya"),

    # North
    # "1240": ("כרמיאל", "Carmiel"),  # TODO: Find correct ID (conflicts with Ra'anana West)
    "5800": ("קריית שמונה", "Kiryat Shmona"),
    # "5900": ("אפרים", "Afri"),  # TODO: Find correct ID (conflicts with Be'er Ya'akov)
    "4680": ("אחיהוד", "Ahihud"),

    # South
    "5900": ("באר יעקב", "Be'er Ya'akov"),
    # "5010": ("יבנה - מזרח", "Yavne - East"),  # TODO: Find correct ID (conflicts with Modi'in Center)
    "5200": ("יבנה - מערב", "Yavne - West"),
    "4100": ("אשדוד - עד הלום", "Ashdod - Ad Halom"),
    # "4900": ("אשקלון", "Ashkelon"),  # TODO: Find correct ID (conflicts with Tel Aviv HaHagana)
    "7300": ("שדרות", "Sderot"),
    "7320": ("נתיבות", "Netivot"),
    "7500": ("באר שבע - מרכז", "Be'er Sheva - Center"),
    "7000": ("באר שבע - צפון/אוניברסיטה", "Be'er Sheva - North/University"),
    "9650": ("דימונה", "Dimona"),
}


def get_train_stations_list():
    """Get list of train stations for dropdown.

    Returns:
        List of dictionaries with 'id', 'name', and 'name_he' keys
    """
    stations = []
    for station_id, (name_he, name_en) in TRAIN_STATIONS.items():
        stations.append({
            'id': station_id,
            'name': f"{name_en} / {name_he}",
            'name_en': name_en,
            'name_he': name_he,
        })

    # Sort by English name
    stations.sort(key=lambda s: s['name_en'])

    return stations


def get_train_station_name(station_id: str) -> tuple[str, str]:
    """Get train station name by ID.

    Args:
        station_id: Train station ID

    Returns:
        Tuple of (Hebrew name, English name), or empty strings if not found
    """
    return TRAIN_STATIONS.get(station_id, ("", ""))

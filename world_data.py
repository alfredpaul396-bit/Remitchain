"""
World data for Xtra: every country with its currency and time zone,
plus stock exchange hours, bank-detail formats and IBAN lengths.
Country names, currencies and time zones come from the Unicode CLDR data
set, through the Babel library.
"""
from datetime import date

from babel import Locale
from babel.core import get_global
from babel.numbers import get_territory_currencies

# Time zone used for countries that have several (the capital's)
_MAIN_ZONE = {
    "AR": "America/Argentina/Buenos_Aires", "AU": "Australia/Sydney", "BR": "America/Sao_Paulo",
    "CA": "America/Toronto", "CD": "Africa/Kinshasa", "CL": "America/Santiago",
    "CN": "Asia/Shanghai", "CY": "Asia/Nicosia", "DE": "Europe/Berlin", "EC": "America/Guayaquil",
    "ES": "Europe/Madrid", "FM": "Pacific/Pohnpei", "GL": "America/Nuuk", "ID": "Asia/Jakarta",
    "KI": "Pacific/Tarawa", "KZ": "Asia/Almaty", "MH": "Pacific/Majuro", "MN": "Asia/Ulaanbaatar",
    "MX": "America/Mexico_City", "MY": "Asia/Kuala_Lumpur", "NZ": "Pacific/Auckland",
    "PF": "Pacific/Tahiti", "PG": "Pacific/Port_Moresby", "PS": "Asia/Hebron", "PT": "Europe/Lisbon",
    "RU": "Europe/Moscow", "UA": "Europe/Kyiv", "US": "America/New_York", "UZ": "Asia/Tashkent",
}
# Regions and uninhabited territories left out
_SKIP = {"AQ", "UM", "BV", "HM", "ZZ", "EU", "EZ", "UN", "QO", "XA", "XB", "IC", "EA", "DG",
         "CP", "TA", "AC", "CQ"}


def _build():
    english = Locale("en")
    zones = get_global("territory_zones")
    countries = {}
    for code, name in english.territories.items():
        if len(code) != 2 or not code.isalpha() or code in _SKIP or code not in zones:
            continue
        try:
            currencies = get_territory_currencies(code, date.today())
        except Exception:
            currencies = []
        countries[code] = {
            "name": name,
            "flag": "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code),
            "currencies": currencies,
            "tz": _MAIN_ZONE.get(code, zones[code][0]),
        }
    return dict(sorted(countries.items(), key=lambda item: item[1]["name"])), dict(english.currencies)


# COUNTRIES[code] = {"name", "flag", "currencies" (official, newest first), "tz"}
COUNTRIES, CURRENCY_NAMES = _build()


# ---------------------------------------------------------------------------
# Main stock exchange per country: name, opening time, closing time (local),
# trading days (0 = Monday ... 6 = Sunday). Main session only: lunch breaks
# and public holidays are not included.
# ---------------------------------------------------------------------------
MON_FRI = (0, 1, 2, 3, 4)
SUN_THU = (6, 0, 1, 2, 3)
EXCHANGES = {
    "IN": ("NSE & BSE (Mumbai)", "09:15", "15:30", MON_FRI),
    "US": ("NYSE & Nasdaq (New York)", "09:30", "16:00", MON_FRI),
    "GB": ("London Stock Exchange", "08:00", "16:30", MON_FRI),
    "FR": ("Euronext Paris", "09:00", "17:30", MON_FRI),
    "DE": ("Deutsche Börse Xetra (Frankfurt)", "09:00", "17:30", MON_FRI),
    "NL": ("Euronext Amsterdam", "09:00", "17:30", MON_FRI),
    "BE": ("Euronext Brussels", "09:00", "17:30", MON_FRI),
    "PT": ("Euronext Lisbon", "08:00", "16:30", MON_FRI),
    "IE": ("Euronext Dublin", "08:00", "16:30", MON_FRI),
    "IT": ("Euronext Milan (Borsa Italiana)", "09:00", "17:30", MON_FRI),
    "ES": ("BME Spanish Exchanges (Madrid)", "09:00", "17:30", MON_FRI),
    "CH": ("SIX Swiss Exchange (Zurich)", "09:00", "17:30", MON_FRI),
    "AT": ("Wiener Börse (Vienna)", "09:00", "17:30", MON_FRI),
    "SE": ("Nasdaq Stockholm", "09:00", "17:30", MON_FRI),
    "DK": ("Nasdaq Copenhagen", "09:00", "17:00", MON_FRI),
    "FI": ("Nasdaq Helsinki", "10:00", "18:30", MON_FRI),
    "NO": ("Euronext Oslo Børs", "09:00", "16:20", MON_FRI),
    "PL": ("Warsaw Stock Exchange", "09:00", "17:00", MON_FRI),
    "TR": ("Borsa Istanbul", "10:00", "18:00", MON_FRI),
    "JP": ("Tokyo Stock Exchange", "09:00", "15:30", MON_FRI),
    "CN": ("Shanghai & Shenzhen Stock Exchanges", "09:30", "15:00", MON_FRI),
    "HK": ("Hong Kong Exchanges (HKEX)", "09:30", "16:00", MON_FRI),
    "SG": ("Singapore Exchange (SGX)", "09:00", "17:00", MON_FRI),
    "KR": ("Korea Exchange (KRX)", "09:00", "15:30", MON_FRI),
    "TW": ("Taiwan Stock Exchange", "09:00", "13:30", MON_FRI),
    "AU": ("Australian Securities Exchange (ASX)", "10:00", "16:00", MON_FRI),
    "NZ": ("NZX (Wellington)", "10:00", "16:45", MON_FRI),
    "CA": ("Toronto Stock Exchange (TSX)", "09:30", "16:00", MON_FRI),
    "MX": ("Bolsa Mexicana de Valores", "08:30", "15:00", MON_FRI),
    "BR": ("B3 (São Paulo)", "10:00", "17:00", MON_FRI),
    "AR": ("BYMA (Buenos Aires)", "11:00", "17:00", MON_FRI),
    "CL": ("Santiago Stock Exchange", "09:30", "16:00", MON_FRI),
    "CO": ("Colombia Stock Exchange (BVC)", "09:30", "16:00", MON_FRI),
    "ZA": ("Johannesburg Stock Exchange (JSE)", "09:00", "17:00", MON_FRI),
    "NG": ("Nigerian Exchange (NGX)", "10:00", "14:30", MON_FRI),
    "KE": ("Nairobi Securities Exchange", "09:00", "15:00", MON_FRI),
    "EG": ("Egyptian Exchange (EGX)", "10:00", "14:30", SUN_THU),
    "MA": ("Casablanca Stock Exchange", "09:30", "15:30", MON_FRI),
    "SA": ("Saudi Exchange (Tadawul)", "10:00", "15:00", SUN_THU),
    "AE": ("ADX & DFM (Abu Dhabi, Dubai)", "10:00", "15:00", MON_FRI),
    "QA": ("Qatar Stock Exchange", "09:30", "13:15", SUN_THU),
    "PK": ("Pakistan Stock Exchange", "09:30", "15:30", MON_FRI),
    "BD": ("Dhaka Stock Exchange", "10:00", "14:30", SUN_THU),
    "LK": ("Colombo Stock Exchange", "09:30", "14:30", MON_FRI),
    "NP": ("Nepal Stock Exchange (NEPSE)", "11:00", "15:00", SUN_THU),
    "ID": ("Indonesia Stock Exchange", "09:00", "16:00", MON_FRI),
    "MY": ("Bursa Malaysia", "09:00", "17:00", MON_FRI),
    "TH": ("Stock Exchange of Thailand", "10:00", "16:30", MON_FRI),
    "PH": ("Philippine Stock Exchange", "09:30", "15:00", MON_FRI),
    "VN": ("Ho Chi Minh Stock Exchange", "09:00", "15:00", MON_FRI),
}

# ---------------------------------------------------------------------------
# Countries that use IBAN, with the IBAN length for each
# ---------------------------------------------------------------------------
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16, "BG": 22,
    "BH": 22, "BY": 28, "CH": 21, "CR": 22, "CY": 28, "CZ": 24, "DE": 22, "DK": 18,
    "DO": 28, "EE": 20, "EG": 29, "ES": 24, "FI": 18, "FO": 18, "FR": 27, "GE": 22,
    "GI": 23, "GL": 18, "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23,
    "IQ": 23, "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24, "ME": 22,
    "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24, "PL": 28,
    "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22, "SA": 24, "SC": 31, "SD": 18,
    "SE": 24, "SI": 19, "SK": 24, "SM": 27, "ST": 25, "SV": 28, "TL": 23, "TN": 24,
    "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}

# ---------------------------------------------------------------------------
# Bank details each country needs (countries not listed here and not using
# IBAN get the international default: bank name, account number, SWIFT/BIC)
# ---------------------------------------------------------------------------
BANK_FORMATS = {
    "IN": ["Account number", "IFSC code"],
    "US": ["ABA routing number", "Account number", "Account type"],
    "GB": ["Sort code", "Account number"],
    "CA": ["Institution number", "Transit number", "Account number"],
    "AU": ["BSB code", "Account number"],
    "NZ": ["Account number"],
    "MX": ["CLABE"],
    "BR": ["Bank code", "Branch number", "Account number", "CPF/CNPJ (tax ID)"],
    "NG": ["Bank name", "NUBAN account number"],
    "ZA": ["Bank name", "Branch code", "Account number"],
    "JP": ["Bank name", "Branch code", "Account number"],
    "PH": ["Bank name", "Account number", "SWIFT/BIC code"],
    "CN": ["Bank name", "Account number", "SWIFT/BIC code"],
}
IBAN_FORMAT = ["IBAN", "SWIFT/BIC code"]
DEFAULT_FORMAT = ["Bank name", "Account number", "SWIFT/BIC code"]

# Destinations blocked for this demo because of broad international sanctions
SANCTIONED = {"KP", "IR", "SY", "CU", "RU", "BY"}

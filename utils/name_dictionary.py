"""
Name Dictionary for Arabic-to-English name conversion.

Contains:
1. ARABIC_TO_ENGLISH: Direct Arabic text to English name mappings
2. VALID_ENGLISH_NAMES: List of valid English names for phonetic correction
3. COMMON_ENGLISH_WORDS: Words to reject if returned by translation (e.g., "Light", "Beautiful")
"""

# =============================================================================
# ARABIC TO ENGLISH DIRECT MAPPINGS
# =============================================================================
# Common Yemen/Arabic names with their standard English spellings.
# This is the "first line of defense" - exact match lookup.

ARABIC_TO_ENGLISH = {
    # Male Names - Very Common
    "محمد": "Mohammed",
    "أحمد": "Ahmed",
    "علي": "Ali",
    "عبدالله": "Abdullah",
    "عبد الله": "Abdullah",
    "خالد": "Khaled",
    "عمر": "Omar",
    "يوسف": "Youssef",
    "إبراهيم": "Ibrahim",
    "ابراهيم": "Ibrahim",
    "حسن": "Hassan",
    "حسين": "Hussein",
    "سعيد": "Saeed",
    "سالم": "Salem",
    "ناصر": "Nasser",
    "صالح": "Saleh",
    "فهد": "Fahd",
    "سلطان": "Sultan",
    "ماجد": "Majed",
    "فيصل": "Faisal",
    "طارق": "Tariq",
    "زيد": "Zaid",
    "عادل": "Adel",
    "سامي": "Sami",
    "وليد": "Waleed",
    "رشيد": "Rashid",
    "جمال": "Jamal",
    "كريم": "Kareem",
    "مصطفى": "Mustafa",
    "قصي": "Qusai",
    "نادر": "Nader",
    "جابر": "Jaber",
    "عبدالجبار": "Abduljabbar",
    "عبدالحميد": "Abdulhamid",
    "عبده": "Abdo",
    "رماح": "Ramah",
    "رمـاح": "Ramah",  # With tatweel
    "عبدالرحمن": "Abdulrahman",
    "عبد الرحمن": "Abdulrahman",
    "عبدالعزيز": "Abdulaziz",
    "عبد العزيز": "Abdulaziz",
    
    # Female Names - Very Common
    "فاطمة": "Fatima",
    "عائشة": "Aisha",
    "مريم": "Maryam",
    "زينب": "Zainab",
    "خديجة": "Khadija",
    "نور": "Noor",
    "سارة": "Sarah",
    "ليلى": "Layla",
    "هدى": "Huda",
    "سلمى": "Salma",
    "أمل": "Amal",
    "منى": "Mona",
    "رانيا": "Rania",
    "دينا": "Dina",
    "نادية": "Nadia",
    "سناء": "Sanaa",
    "هناء": "Hanaa",
    "جميلة": "Jamila",
    "كريمة": "Karima",
    "حليمة": "Halima",
    "آمنة": "Amina",
    "امنة": "Amina",
    "رقية": "Ruqaya",
    "سمية": "Sumaya",
    "عفاف": "Afaf",
    "نجاة": "Najat",
    "سميرة": "Samira",
    "سماح": "Samah",
    
    # Common Family/Tribal Names
    "الحسني": "Al-Hasani",
    "الأحمدي": "Al-Ahmadi",
    "العمري": "Al-Omari",
    "الصالحي": "Al-Salehi",
    "المحمدي": "Al-Mohammadi",
    "القحطاني": "Al-Qahtani",
    "الغامدي": "Al-Ghamdi",
    "الزهراني": "Al-Zahrani",
    "الشهري": "Al-Shehri",
    "الدوسري": "Al-Dosari",
}

# =============================================================================
# VALID ENGLISH NAMES FOR PHONETIC CORRECTION
# =============================================================================
# Used by Double Metaphone to "snap" imperfect transliterations to valid names.
# e.g., "Jmila" snaps to "Jamila" because they have the same Metaphone code.

VALID_ENGLISH_NAMES = [
    # Male
    "Mohammed", "Muhammad", "Mohamed", "Ahmad", "Ahmed", "Ali", "Abdullah",
    "Khaled", "Khalid", "Omar", "Umar", "Youssef", "Yousef", "Joseph",
    "Ibrahim", "Abraham", "Hassan", "Hasan", "Hussein", "Hussain",
    "Saeed", "Said", "Salem", "Salim", "Nasser", "Nasir", "Saleh", "Salih",
    "Fahd", "Fahad", "Sultan", "Majed", "Majid", "Faisal", "Faysal",
    "Tariq", "Tarek", "Zaid", "Zayd", "Adel", "Adil", "Sami", "Sammy",
    "Waleed", "Walid", "Rashid", "Rasheed", "Jamal", "Kamal",
    "Kareem", "Karim", "Mustafa", "Mustapha",
    
    # Female
    "Fatima", "Fatimah", "Aisha", "Aysha", "Maryam", "Mariam", "Mary",
    "Zainab", "Zaynab", "Khadija", "Khadijah", "Noor", "Nour", "Nur",
    "Sarah", "Sara", "Layla", "Leila", "Laila", "Huda", "Houda",
    "Salma", "Selma", "Amal", "Amaal", "Mona", "Muna", "Rania", "Raniya",
    "Dina", "Deena", "Nadia", "Nadya", "Sanaa", "Sana", "Hanaa", "Hana",
    "Jamila", "Jameela", "Karima", "Kareema", "Halima", "Haleema",
    "Amina", "Aminah", "Ameena", "Ruqaya", "Ruqayyah", "Sumaya", "Sumayyah",
    "Afaf", "Najat", "Najaat", "Samira", "Sameera",
]

# =============================================================================
# COMMON ENGLISH WORDS TO REJECT
# =============================================================================
# If Google Translate returns one of these, it's translating the MEANING
# not the NAME. We should reject and use phonetic mapping instead.

COMMON_ENGLISH_WORDS = {
    # Nature/Beauty words (common Arabic name meanings)
    "light", "moon", "star", "sun", "sky", "flower", "rose", "pearl",
    "beautiful", "beauty", "pretty", "handsome", "kind", "generous",
    "lion", "tiger", "eagle", "falcon", "hawk",
    "happiness", "happy", "joy", "hope", "faith", "peace",
    "noble", "precious", "beloved", "dear", "sweet",
    "gift", "blessing", "fortune", "luck", "victory",
    "river", "sea", "ocean", "mountain", "garden", "paradise",
    "gold", "silver", "diamond", "ruby", "emerald",
    "king", "queen", "prince", "princess", "leader",
}


def get_arabic_to_english(arabic_name: str) -> str | None:
    """
    Look up Arabic name in dictionary.
    Returns English equivalent or None if not found.
    """
    # Normalize: strip whitespace
    arabic_name = arabic_name.strip()
    return ARABIC_TO_ENGLISH.get(arabic_name)


def is_rejected_word(english_word: str) -> bool:
    """
    Check if an English word should be rejected as a translation.
    Returns True if it's a common word (meaning translation, not name).
    """
    return english_word.lower().strip() in COMMON_ENGLISH_WORDS

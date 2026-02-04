"""
Yemen Governorates and Districts Reference Data

Provides reference data for Place of Birth validation:
- 22 Governorates with Arabic names and variants
- Major districts within each governorate
- Used for token classification and matching
"""

# Yemen's 22 Governorates with common spelling variants and major districts
YEMEN_LOCATIONS = {
    "governorates": {
        "صنعاء": {
            "name_en": "Sana'a",
            "variants": ["صنعاء", "صنعا", "أمانة العاصمة"],
            "districts": ["بني الحارث", "معين", "الثورة", "التحرير", "الصافية", "شعوب", "السبعين", "الوحدة", "آزال", "صنعاء القديمة"]
        },
        "عدن": {
            "name_en": "Aden",
            "variants": ["عدن"],
            "districts": ["كريتر", "المعلا", "التواهي", "صيرة", "الشيخ عثمان", "المنصورة", "دار سعد", "البريقة"]
        },
        "تعز": {
            "name_en": "Taiz",
            "variants": ["تعز"],
            "districts": ["القاهرة", "المظفر", "صالة", "الشمايتين", "الوازعية", "جبل حبشي", "المواسط", "الصلو"]
        },
        "الحديدة": {
            "name_en": "Hodeidah",
            "variants": ["الحديدة", "الحديده", "حديدة"],
            "districts": ["الحديدة", "باجل", "زبيد", "اللحية", "الزهرة", "الزيدية", "الحوك", "بيت الفقيه"]
        },
        "إب": {
            "name_en": "Ibb",
            "variants": ["إب", "اب"],
            "districts": ["إب", "جبلة", "ذي السفال", "يريم", "النادرة", "السياني", "العدين", "بعدان"]
        },
        "ذمار": {
            "name_en": "Dhamar",
            "variants": ["ذمار"],
            "districts": ["ذمار", "عنس", "جهران", "مغرب عنس", "عتمة", "وصاب السافل", "الحدا"]
        },
        "حضرموت": {
            "name_en": "Hadramaut",
            "variants": ["حضرموت", "حضرموت"],
            "districts": ["المكلا", "سيئون", "شبام", "تريم", "الشحر", "ساه", "القطن", "دوعن", "غيل باوزير"]
        },
        "المحويت": {
            "name_en": "Al Mahwit",
            "variants": ["المحويت", "محويت"],
            "districts": ["المحويت", "الرجم", "حفاش", "شبام كوكبان", "ملحان", "بني سعد"]
        },
        "صعدة": {
            "name_en": "Saada",
            "variants": ["صعدة", "صعده"],
            "districts": ["صعدة", "حيدان", "رازح", "البقع", "كتاف", "منبه", "قطابر"]
        },
        "عمران": {
            "name_en": "Amran",
            "variants": ["عمران"],
            "districts": ["عمران", "خمر", "حرف سفيان", "ثلا", "رداع", "سحار"]
        },
        "الجوف": {
            "name_en": "Al Jawf",
            "variants": ["الجوف", "جوف"],
            "districts": ["الحزم", "الغيل", "برط العنان", "خب والشعف", "المتون", "المصلوب"]
        },
        "حجة": {
            "name_en": "Hajjah",
            "variants": ["حجة", "حجه"],
            "districts": ["حجة", "عبس", "قارة", "كحلان عفار", "مبين", "حرض", "ميدي", "كشر"]
        },
        "لحج": {
            "name_en": "Lahij",
            "variants": ["لحج", "لحي"],
            "districts": ["الحوطة", "تبن", "يافع", "يهر", "الحد", "المفلحي", "الملاح"]
        },
        "مأرب": {
            "name_en": "Marib",
            "variants": ["مأرب", "مارب"],
            "districts": ["مأرب", "حريب", "صرواح", "مدغل", "رحبة", "الجوبة"]
        },
        "ريمة": {
            "name_en": "Raymah",
            "variants": ["ريمة", "ريمه"],
            "districts": ["الجبين", "كسمة", "السلفية", "بلاد الطعام", "الجعفرية", "مزهر"]
        },
        "أبين": {
            "name_en": "Abyan",
            "variants": ["أبين", "ابين"],
            "districts": ["زنجبار", "جعار", "لودر", "أحور", "المحفد", "سباح"]
        },
        "البيضاء": {
            "name_en": "Al Bayda",
            "variants": ["البيضاء", "بيضاء"],
            "districts": ["البيضاء", "رداع", "السوادية", "قيفة", "ذي ناعم", "مكيراس"]
        },
        "المهرة": {
            "name_en": "Al Mahrah",
            "variants": ["المهرة", "مهرة"],
            "districts": ["الغيضة", "سيحوت", "حصوين", "قشن", "شحن", "حات"]
        },
        "شبوة": {
            "name_en": "Shabwah",
            "variants": ["شبوة", "شبوه"],
            "districts": ["عتق", "حبان", "عرما", "بيحان", "الروضة", "ميفع", "رضوم"]
        },
        "الضالع": {
            "name_en": "Al Dhale'e",
            "variants": ["الضالع", "ضالع"],
            "districts": ["الضالع", "قعطبة", "جبن", "دمت", "الحشاء", "الأزارق"]
        },
        "سقطرى": {
            "name_en": "Socotra",
            "variants": ["سقطرى", "سقطري"],
            "districts": ["حديبو", "قلنسيه", "عبد الكوري", "مومي"]
        },
        "الحديدة": {
            "name_en": "Hodeidah",
            "variants": ["الحديدة", "حديدة"],
            "districts": ["الحديدة", "باجل", "زبيد", "اللحية", "الزهرة", "المنيرة"]
        }
    }
}


def get_all_governorate_names() -> set:
    """Get all governorate names including variants."""
    names = set()
    for gov_data in YEMEN_LOCATIONS["governorates"].values():
        names.update(gov_data["variants"])
    return names


def get_all_district_names() -> set:
    """Get all district names."""
    districts = set()
    for gov_data in YEMEN_LOCATIONS["governorates"].values():
        districts.update(gov_data["districts"])
    return districts


def find_governorate_by_name(name: str) -> tuple[str | None, dict | None]:
    """
    Find governorate by name or variant.
    
    Returns: (canonical_name, governorate_data) or (None, None)
    """
    name_normalized = name.strip()
    for canonical_name, gov_data in YEMEN_LOCATIONS["governorates"].items():
        if name_normalized in gov_data["variants"] or name_normalized == canonical_name:
            return canonical_name, gov_data
    return None, None


def find_district_governorate(district: str) -> str | None:
    """
    Find which governorate a district belongs to.
    
    Returns: governorate canonical name or None
    """
    district_normalized = district.strip()
    for canonical_name, gov_data in YEMEN_LOCATIONS["governorates"].items():
        if district_normalized in gov_data["districts"]:
            return canonical_name
    return None

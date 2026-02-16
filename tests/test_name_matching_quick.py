"""Quick verification of the new name matching service."""
from services.name_matching_service import compare_names

tests = [
    ("Mohammed Ali", "Mohammed Ali", "english", "Exact match"),
    ("Mohammed Ali", "Ali Mohammed", "english", "Reversed order"),
    ("Mohammed", "Muhammad", "english", "Transliteration"),
    ("البريهي", "البرهي", "arabic", "Arabic OCR typo"),
    ("مرام رائد السقاف", "السقاف مرام رائد", "arabic", "Arabic reversed"),
    ("Eid Allah", "Abdullah", "english", "Eid Allah vs Abdullah"),
    ("Maram Raed Alsqaf", "Alsqaf Maram Raed", "english", "Full name reorder"),
    ("Mohammed Ali", "Sarah Ahmed", "english", "Completely different"),
    ("Maram Raed Abdalmola Alsqaf", "Alsqaf Maram Raed", "english", "Partial + reorder"),
]

for ocr, user, lang, label in tests:
    r = compare_names(ocr, user, lang)
    tier = r["match_tier"]
    score = r["final_score"]
    print(f"{label:30s} | tier={tier:10s} | score={score:.2f}")

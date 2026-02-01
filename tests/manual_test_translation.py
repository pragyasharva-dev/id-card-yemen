"""
Script to verify hybrid translation on specific user-provided names.
"""
import sys
import codecs
from services.translation_service import hybrid_name_convert

# Force UTF-8 for Windows console
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')

NAMES_TO_TEST = [
    "قصي إبراهيم عبدالجبار احمد الكنيعي",
    "سماح جابر علي جابر الرحبي",
    "نادر عبدالحميد محمد عبدالله",
    "رمـاح عبده علي الرزاعي"
]

print(f"{'Arabic Name':<40} | {'English Result':<40} | {'Method'}")
print("-" * 100)

for full_name in NAMES_TO_TEST:
    # Split full name into parts to translate word-by-word (simulating field-level translation)
    # The hybrid function works on single names/words best, or full strings.
    # Let's try passing the full string first.
    
    result = hybrid_name_convert(full_name)
    print(f"{full_name:<40} | {result['english']:<40} | {result['method']}")
    
    # Also print word-by-word breakdown for debugging
    print("   Breakdown:")
    for part in full_name.split():
        part_res = hybrid_name_convert(part)
        print(f"   - {part:<15} -> {part_res['english']:<15} ({part_res['method']})")
    print("-" * 100)

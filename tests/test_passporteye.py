"""
PassportEye MRZ Testing Script

Standalone script to test PassportEye library for MRZ detection.
This is for testing only - NOT integrated into main pipeline.

Usage:
    python tests/test_passporteye.py <passport_image_path>
    
Example:
    python tests/test_passporteye.py sample_images/passport.jpg
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_passporteye(image_path: str):
    """Test PassportEye MRZ detection and extraction on a passport image."""
    
    print("=" * 60)
    print("🛂 PassportEye MRZ Extraction Test")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"❌ Error: File not found: {image_path}")
        return None
    
    print(f"\n📂 Testing image: {image_path}")
    
    # Try importing PassportEye
    try:
        from passporteye import read_mrz
        print("✅ PassportEye imported successfully")
    except ImportError as e:
        print(f"❌ PassportEye not installed: {e}")
        print("\n💡 Install with: pip install passporteye")
        return None
    
    # Check for Tesseract
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        print("✅ Tesseract OCR found")
    except Exception as e:
        print(f"⚠️ Tesseract warning: {e}")
        print("💡 Install Tesseract: https://github.com/UB-Mannheim/tesseract")
    
    print("\n🔍 Detecting and extracting MRZ...")
    print("-" * 40)
    
    # Read MRZ
    try:
        mrz = read_mrz(image_path)
        
        if mrz is None:
            print("❌ No MRZ detected in image")
            print("\n💡 Tips:")
            print("   - Ensure passport is flat and well-lit")
            print("   - MRZ (bottom text) should be clearly visible")
            print("   - Try a higher resolution image")
            return None
        
        # Get MRZ data from PassportEye
        mrz_data = mrz.to_dict()
        
        print("✅ MRZ Extracted Successfully!\n")
        
        # Display extracted data
        print("📋 EXTRACTED PASSPORT DATA:")
        print("-" * 40)
        
        # Format and display fields
        passport_number = mrz_data.get('number', 'N/A')
        surname = mrz_data.get('surname', 'N/A')
        given_names = mrz_data.get('names', 'N/A')
        full_name = f"{given_names} {surname}".strip()
        nationality = mrz_data.get('nationality', 'N/A')
        country = mrz_data.get('country', 'N/A')
        dob = format_date(mrz_data.get('date_of_birth'))
        expiry = format_date(mrz_data.get('expiration_date'))
        sex = mrz_data.get('sex', 'N/A')
        gender = 'Male' if sex == 'M' else 'Female' if sex == 'F' else sex
        valid_score = mrz_data.get('valid_score', 0)
        
        fields = [
            ("Passport Number", passport_number),
            ("Surname", surname),
            ("Given Names", given_names),
            ("Full Name", full_name),
            ("Nationality", nationality),
            ("Country Code", country),
            ("Date of Birth", dob),
            ("Expiry Date", expiry),
            ("Gender", gender),
            ("MRZ Valid Score", f"{valid_score}%"),
        ]
        
        for label, value in fields:
            print(f"  {label:20}: {value}")
        
        # Show raw MRZ text
        if hasattr(mrz, 'aux') and mrz.aux:
            raw_text = mrz.aux.get('raw_text', '')
            if raw_text:
                print("\n📝 RAW MRZ LINES:")
                print("-" * 40)
                for line in raw_text.split('\n'):
                    if line.strip():
                        print(f"  {line}")
        
        # Validation status
        print("\n📊 VALIDATION:")
        print("-" * 40)
        if valid_score >= 80:
            print(f"  Status: ✅ HIGH CONFIDENCE ({valid_score}%)")
        elif valid_score >= 50:
            print(f"  Status: ⚠️ MEDIUM CONFIDENCE ({valid_score}%)")
        else:
            print(f"  Status: ❌ LOW CONFIDENCE ({valid_score}%)")
        
        print("\n" + "=" * 60)
        print("✅ EXTRACTION COMPLETE")
        print("=" * 60)
        
        # Return structured data
        return {
            "success": True,
            "passport_number": passport_number,
            "surname": surname,
            "given_names": given_names,
            "full_name_english": full_name,
            "nationality": nationality,
            "country_code": country,
            "date_of_birth": dob,
            "expiry_date": expiry,
            "gender": gender,
            "mrz_valid": valid_score >= 50,
            "confidence": valid_score / 100,
            "raw_mrz": mrz.aux.get('raw_text', '') if hasattr(mrz, 'aux') else None
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def format_date(date_str: str) -> str:
    """Format MRZ date (YYMMDD) to readable format."""
    if not date_str or len(date_str) != 6:
        return date_str or 'N/A'
    
    try:
        yy = int(date_str[0:2])
        mm = date_str[2:4]
        dd = date_str[4:6]
        
        yyyy = 2000 + yy if yy <= 40 else 1900 + yy
        return f"{yyyy}-{mm}-{dd}"
    except:
        return date_str


def compare_methods(image_path: str):
    """Compare PassportEye with our pixel-based method."""
    
    print("\n" + "=" * 60)
    print("⚖️ COMPARISON: PassportEye vs Pixel-Based")
    print("=" * 60)
    
    import cv2
    from services.passport_mrz_parser import parse_passport_mrz
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print("❌ Failed to load image")
        return
    
    # Method 1: PassportEye
    print("\n📌 Method 1: PassportEye")
    print("-" * 40)
    passporteye_result = test_passporteye_silent(image_path)
    
    # Method 2: Pixel-based
    print("\n📌 Method 2: Pixel-Based (Bottom 25%)")
    print("-" * 40)
    pixel_result = test_pixel_based(image)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"  PassportEye: {'✅ Success' if passporteye_result else '❌ Failed'}")
    print(f"  Pixel-Based: {'✅ Success' if pixel_result else '❌ Failed'}")


def test_passporteye_silent(image_path: str):
    """Test PassportEye without verbose output."""
    try:
        from passporteye import read_mrz
        mrz = read_mrz(image_path)
        if mrz:
            data = mrz.to_dict()
            print(f"  Passport: {data.get('number')}")
            print(f"  Name: {data.get('names')} {data.get('surname')}")
            print(f"  DOB: {format_date(data.get('date_of_birth'))}")
            return data
        else:
            print("  No MRZ detected")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def test_pixel_based(image):
    """Test pixel-based MRZ extraction."""
    try:
        import cv2
        from services.ocr_service import get_ocr_service
        from services.passport_mrz_parser import parse_passport_mrz
        
        height, width = image.shape[:2]
        mrz_start = int(height * 0.75)
        mrz_region = image[mrz_start:height, :]
        
        gray = cv2.cvtColor(mrz_region, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        ocr = get_ocr_service()
        result = ocr.ocr(thresh, cls=False)
        
        if not result or not result[0]:
            print("  No text detected in MRZ region")
            return None
        
        mrz_lines = []
        for line in result[0]:
            if line[1][0]:
                text = line[1][0].strip().upper()
                if len(text) >= 40:
                    mrz_lines.append(text)
        
        if len(mrz_lines) >= 2:
            # Clean lines to 44 chars
            cleaned = [line[:44].ljust(44, '<') for line in mrz_lines[:2]]
            parsed = parse_passport_mrz(cleaned)
            
            if parsed.get('success'):
                print(f"  Passport: {parsed.get('passport_number')}")
                print(f"  Name: {parsed.get('full_name_english')}")
                print(f"  DOB: {parsed.get('date_of_birth')}")
                return parsed
            else:
                print(f"  Parse error: {parsed.get('error')}")
                return None
        else:
            print(f"  Found {len(mrz_lines)} MRZ lines (need 2)")
            return None
            
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_passporteye.py <passport_image_path>")
        print("\nExample:")
        print("  python test_passporteye.py sample_images/passport.jpg")
        print("\nOptions:")
        print("  --compare  Compare PassportEye with pixel-based method")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if "--compare" in sys.argv:
        compare_methods(image_path)
    else:
        test_passporteye(image_path)

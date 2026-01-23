# Yemen ID Document Database Schema

## Overview

This project uses **SQLite databases** to store Yemen National ID Card, Passport, and Verification data.

**Database Files:**
- `data/databases/yemen_id_cards.db` - ID Card records
- `data/databases/yemen_passports.db` - Passport records
- `data/databases/verification_results.db` - Verification results

---

## ID Card Schema (`id_cards` table) - 18 columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `national_id` | TEXT | 11-digit Yemen ID number (UNIQUE) |
| `first_name_arabic` | TEXT | الاسم الأول |
| `middle_name_arabic` | TEXT | اسم الأب / الجد |
| `last_name_arabic` | TEXT | اسم العائلة |
| `first_name_english` | TEXT | First name |
| `middle_name_english` | TEXT | Middle name |
| `last_name_english` | TEXT | Last/family name |
| `date_of_birth` | TEXT | YYYY-MM-DD format |
| `place_of_birth` | TEXT | مكان الميلاد |
| `gender` | TEXT | Male / Female |
| `blood_group` | TEXT | A+, B-, O+, AB-, etc. |
| `issuance_date` | TEXT | YYYY-MM-DD |
| `expiry_date` | TEXT | YYYY-MM-DD |
| `front_image_blob` | BLOB | Front image (JPEG) |
| `back_image_blob` | BLOB | Back image (JPEG) |
| `selfie_image_blob` | BLOB | Selfie image (JPEG) |
| `created_at` | TEXT | Auto timestamp |

---

## Passport Schema (`passports` table) - 20 columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `passport_number` | TEXT | Passport number (UNIQUE) |
| `surname_arabic` | TEXT | اسم العائلة |
| `given_names_arabic` | TEXT | الأسماء المعطاة |
| `surname_english` | TEXT | Surname/Family name |
| `given_names_english` | TEXT | Given names |
| `profession` | TEXT | Occupation/Job |
| `date_of_birth` | TEXT | YYYY-MM-DD format |
| `place_of_birth` | TEXT | مكان الميلاد |
| `gender` | TEXT | Male / Female |
| `blood_group` | TEXT | A+, B-, O+, AB-, etc. |
| `passport_type` | TEXT | Ordinary / Diplomatic / Service |
| `issuance_date` | TEXT | YYYY-MM-DD |
| `expiry_date` | TEXT | YYYY-MM-DD |
| `issuing_authority` | TEXT | Authority that issued passport |
| `mrz_line_1` | TEXT | Machine Readable Zone line 1 |
| `mrz_line_2` | TEXT | Machine Readable Zone line 2 |
| `passport_image_blob` | BLOB | Passport image (JPEG) |
| `selfie_image_blob` | BLOB | Selfie image (JPEG) |
| `created_at` | TEXT | Auto timestamp |

---

## Verification Schema (`verifications` table) - 24 columns

Stores verification results when selfie is matched against ID/passport.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `document_type` | TEXT | 'id_card' or 'passport' |
| `document_id` | TEXT | national_id or passport_number |
| `first_name_arabic` | TEXT | From ID card |
| `middle_name_arabic` | TEXT | From ID card |
| `last_name_arabic` | TEXT | From ID card |
| `first_name_english` | TEXT | From ID card |
| `middle_name_english` | TEXT | From ID card |
| `last_name_english` | TEXT | From ID card |
| `surname_arabic` | TEXT | From passport |
| `given_names_arabic` | TEXT | From passport |
| `surname_english` | TEXT | From passport |
| `given_names_english` | TEXT | From passport |
| `profession` | TEXT | From passport |
| `date_of_birth` | TEXT | From source document |
| `place_of_birth` | TEXT | From source document |
| `gender` | TEXT | From source document |
| `blood_group` | TEXT | From source document |
| `verification_status` | TEXT | 'verified' / 'failed' / 'pending' |
| `similarity_score` | REAL | Face match score (0.0 - 1.0) |
| `selfie_image_blob` | BLOB | Selfie used for verification |
| `document_image_blob` | BLOB | ID/passport image used |
| `verified_at` | TEXT | When verification succeeded |
| `created_at` | TEXT | Auto timestamp |

---

## Python Usage

```python
from services.database import get_id_card_db, get_passport_db, get_verification_db

# ID Card
db = get_id_card_db()
db.insert({"national_id": "12345678901", "name_arabic": "أحمد محمد علي"})

# Passport
db = get_passport_db()
db.insert({"passport_number": "A12345678", "surname_english": "AL-HASANI"})

# Verification
db = get_verification_db()
db.insert({"document_type": "id_card", "document_id": "12345678901", "verification_status": "verified", "similarity_score": 0.92})
```

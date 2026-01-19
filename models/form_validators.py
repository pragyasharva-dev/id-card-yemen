"""
Form Validation Models for Yemen ID Cards and Passports.

Provides production-level Pydantic validators for:
- Yemen National ID form data
- Yemen Passport form data
- Name validation (alphabets, spaces, hyphens only)
- Date validation (proper format and range checking)
- ID number validation with regex patterns
"""
from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class YemenNationalIDForm(BaseModel):
    """
    Form validation model for Yemen National ID card data entry.
    
    Implements production-level validation rules:
    - Name: Alphabets (English/Arabic), spaces, hyphens only
    - Dates: YYYY-MM-DD format with realistic range checking  
    - ID Number: 11 digits, numeric only
    - Gender: AUTO-DERIVED from 4th digit of ID number (odd=Male, even=Female)
      Note: Yemen National ID cards do NOT have pre-written gender
    """
    
    # Required fields
    id_number: str = Field(
        ...,
        description="Yemen National ID number (11 digits)",
        min_length=11,
        max_length=11
    )
    
    name_arabic: str = Field(
        ...,
        description="Full name in Arabic script",
        min_length=2,
        max_length=100
    )
    
    name_english: str = Field(
        ...,
        description="Full name in English/Latin script",
        min_length=2,
        max_length=100
    )
    
    date_of_birth: str = Field(
        ...,
        description="Date of birth in YYYY-MM-DD format"
    )
    
    gender: Optional[Literal["Male", "Female"]] = Field(
        None,
        description="Gender - AUTO-DERIVED from 4th digit of ID number (do not input manually)"
    )
    
    # Optional fields
    place_of_birth: Optional[str] = Field(
        None,
        description="Place of birth",
        min_length=2,
        max_length=100
    )
    
    issuance_date: Optional[str] = Field(
        None,
        description="ID card issuance date in YYYY-MM-DD format"
    )
    
    expiry_date: Optional[str] = Field(
        None,
        description="ID card expiry date in YYYY-MM-DD format"
    )
    
    # Validators
    @field_validator('id_number')
    @classmethod
    def validate_id_number(cls, v: str) -> str:
        """Validate Yemen National ID number: 11 digits, numeric only."""
        # Remove any whitespace
        v = v.strip()
        
        # Check pattern: exactly 11 digits
        pattern = r'^\d{11}$'
        if not re.match(pattern, v):
            raise ValueError(
                'Yemen National ID number must be exactly 11 digits (numeric only). '
                f'Received: {v}'
            )
        
        return v
    
    @model_validator(mode='after')
    def derive_gender_from_id(self):
        """
        Auto-derive gender from 4th digit of Yemen National ID number.
        
        Logic: 
        - If gender is already provided manually, keep it
        - If gender is NOT provided, auto-derive from 4th digit (BINARY ONLY)
          - 0 = Female
          - 1 = Male
        
        Yemen National ID cards do NOT have pre-written gender on the physical card.
        The 4th digit MUST be 0 or 1 only.
        """
        # Only auto-derive if gender is not already provided
        if self.gender is None and self.id_number and len(self.id_number) >= 4:
            fourth_digit = int(self.id_number[3])  # 4th digit (0-indexed)
            
            # Strict binary check
            if fourth_digit == 1:
                self.gender = "Male"
            elif fourth_digit == 0:
                self.gender = "Female"
            else:
                raise ValueError(
                    f"Invalid Yemen National ID: 4th digit must be 0 (Female) or 1 (Male). "
                    f"Received 4th digit: {fourth_digit} in ID: {self.id_number}"
                )
        
        return self
    
    @field_validator('name_arabic', 'name_english')
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        """
        Validate name fields: alphabets (English/Arabic), spaces, hyphens only.
        No numbers or special characters allowed.
        """
        v = v.strip()
        
        # Pattern: Arabic unicode range + Latin letters + spaces + hyphens
        # Arabic range: \u0600-\u06FF (Arabic block)
        # Arabic supplement: \u0750-\u077F
        # Arabic Extended-A: \u08A0-\u08FF
        # Also include Arabic tatweel: \u0640
        pattern = r'^[a-zA-Z\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0640\s\-]+$'
        
        if not re.match(pattern, v):
            field_name = info.field_name
            raise ValueError(
                f'{field_name} must contain only alphabets (English or Arabic), '
                f'spaces, and hyphens. No numbers or special characters allowed. '
                f'Received: {v}'
            )
        
        # Check minimum length after stripping
        if len(v) < 2:
            raise ValueError(f'{info.field_name} must be at least 2 characters long')
        
        return v
    
    @field_validator('place_of_birth')
    @classmethod
    def validate_place_of_birth(cls, v: Optional[str]) -> Optional[str]:
        """Validate place of birth: alphabets, spaces, hyphens, commas only."""
        if v is None:
            return v
        
        v = v.strip()
        
        # Pattern: Arabic + Latin + spaces + hyphens + commas
        pattern = r'^[a-zA-Z\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0640\s\-,]+$'
        
        if not re.match(pattern, v):
            raise ValueError(
                'Place of birth must contain only alphabets (English or Arabic), '
                f'spaces, hyphens, and commas. Received: {v}'
            )
        
        if len(v) < 2:
            raise ValueError('Place of birth must be at least 2 characters long')
        
        return v
    
    @field_validator('date_of_birth', 'issuance_date', 'expiry_date')
    @classmethod
    def validate_date_format(cls, v: Optional[str], info) -> Optional[str]:
        """
        Validate date fields: YYYY-MM-DD format with realistic range checking.
        
        - Date of birth: Between 1900-01-01 and today, age 0-120 years
        - Issuance date: Between 1990-01-01 and today
        - Expiry date: Between today and 50 years from today
        """
        if v is None:
            return v
        
        v = v.strip()
        field_name = info.field_name
        
        # Validate format
        try:
            date_obj = datetime.strptime(v, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(
                f'{field_name} must be in YYYY-MM-DD format. '
                f'Example: 1990-05-15. Received: {v}'
            )
        
        today = date.today()
        
        # Range validation based on field type
        if field_name == 'date_of_birth':
            min_date = date(1900, 1, 1)
            max_date = today
            
            if date_obj < min_date or date_obj > max_date:
                raise ValueError(
                    f'Date of birth must be between {min_date} and {max_date}. '
                    f'Received: {v}'
                )
            
            # Check realistic age (0-120 years)
            age_years = (today - date_obj).days / 365.25
            if age_years > 120:
                raise ValueError(
                    f'Date of birth indicates age over 120 years, which is unrealistic. '
                    f'Received: {v}'
                )
        
        elif field_name == 'issuance_date':
            min_date = date(1990, 1, 1)  # Yemen IDs started around this time
            max_date = today
            
            if date_obj < min_date or date_obj > max_date:
                raise ValueError(
                    f'Issuance date must be between {min_date} and {max_date}. '
                    f'Received: {v}'
                )
        
        elif field_name == 'expiry_date':
            min_date = today
            max_date = date(today.year + 50, today.month, today.day)
            
            if date_obj < min_date or date_obj > max_date:
                raise ValueError(
                    f'Expiry date must be between {min_date} (today) and {max_date}. '
                    f'Received: {v}'
                )
        
        return v
    
    def validate_date_logic(self):
        """Validate logical relationships between dates."""
        # If both issuance and expiry dates are provided, expiry must be after issuance
        if self.issuance_date and self.expiry_date:
            issuance = datetime.strptime(self.issuance_date, '%Y-%m-%d').date()
            expiry = datetime.strptime(self.expiry_date, '%Y-%m-%d').date()
            
            if expiry <= issuance:
                raise ValueError(
                    'Expiry date must be after issuance date. '
                    f'Issuance: {self.issuance_date}, Expiry: {self.expiry_date}'
                )
        
        # Date of birth should be before issuance date (if provided)
        if self.issuance_date:
            dob = datetime.strptime(self.date_of_birth, '%Y-%m-%d').date()
            issuance = datetime.strptime(self.issuance_date, '%Y-%m-%d').date()
            
            if dob >= issuance:
                raise ValueError(
                    'Date of birth must be before issuance date. '
                    f'DOB: {self.date_of_birth}, Issuance: {self.issuance_date}'
                )
        
        return self


class YemenPassportForm(BaseModel):
    """
    Form validation model for Yemen Passport data entry.
    
    Passport number format: 8 digits, numeric only
    Gender: Pre-written on passport (user must input)
    Other validations similar to National ID
    """
    
    # Required fields
    passport_number: str = Field(
        ...,
        description="Yemen Passport number (8 digits)",
        min_length=8,
        max_length=8
    )
    
    name_arabic: str = Field(
        ...,
        description="Full name in Arabic script",
        min_length=2,
        max_length=100
    )
    
    name_english: str = Field(
        ...,
        description="Full name in English/Latin script",
        min_length=2,
        max_length=100
    )
    
    date_of_birth: str = Field(
        ...,
        description="Date of birth in YYYY-MM-DD format"
    )
    
    gender: Literal["Male", "Female"] = Field(
        ...,
        description="Gender - must be 'Male' or 'Female'"
    )
    
    # Optional fields
    place_of_birth: Optional[str] = Field(
        None,
        description="Place of birth",
        min_length=2,
        max_length=100
    )
    
    issuance_date: Optional[str] = Field(
        None,
        description="Passport issuance date in YYYY-MM-DD format"
    )
    
    expiry_date: Optional[str] = Field(
        None,
        description="Passport expiry date in YYYY-MM-DD format"
    )
    
    # Validators
    @field_validator('passport_number')
    @classmethod
    def validate_passport_number(cls, v: str) -> str:
        """Validate Yemen Passport number: 8 digits, numeric only."""
        v = v.strip()
        
        # Check pattern: exactly 8 digits
        pattern = r'^\d{8}$'
        if not re.match(pattern, v):
            raise ValueError(
                'Yemen Passport number must be exactly 8 digits (numeric only). '
                f'Received: {v}'
            )
        
        return v
    
    # Copy validators from YemenNationalIDForm with proper decorators
    @field_validator('name_arabic', 'name_english')
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        """Validate name fields: alphabets (English/Arabic), spaces, hyphens only."""
        return YemenNationalIDForm.validate_name.__func__(cls, v, info)
    
    @field_validator('place_of_birth')
    @classmethod
    def validate_place_of_birth(cls, v: Optional[str]) -> Optional[str]:
        """Validate place of birth: alphabets, spaces, hyphens, commas only."""
        return YemenNationalIDForm.validate_place_of_birth.__func__(cls, v)
    
    @field_validator('date_of_birth', 'issuance_date', 'expiry_date')
    @classmethod
    def validate_date_format(cls, v: Optional[str], info) -> Optional[str]:
        """Validate date fields: YYYY-MM-DD format with realistic range checking."""
        return YemenNationalIDForm.validate_date_format.__func__(cls, v, info)
    
    @model_validator(mode='after')
    def validate_date_logic(self):
        """Validate logical relationships between dates."""
        return YemenNationalIDForm.validate_date_logic(self)


class IDFormSubmitRequest(BaseModel):
    """
    Request wrapper for ID form submission.
    Determines which validation schema to apply based on id_type.
    
    IMPORTANT:
    - For yemen_national_id: Gender is AUTO-DERIVED from 4th digit of ID number (do NOT send gender)
    - For yemen_passport: Gender is REQUIRED (pre-written on passport)
    """
    
    id_type: Literal["yemen_national_id", "yemen_passport"] = Field(
        ...,
        description="Type of ID card: 'yemen_national_id' or 'yemen_passport'"
    )
    
    # National ID fields
    id_number: Optional[str] = Field(
        None,
        description="Yemen National ID number (required for yemen_national_id)"
    )
    
    # Passport fields  
    passport_number: Optional[str] = Field(
        None,
        description="Yemen Passport number (required for yemen_passport)"
    )
    
    # Common fields
    name_arabic: str = Field(..., description="Full name in Arabic")
    name_english: str = Field(..., description="Full name in English")
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    
    # Gender: Optional for National ID (manual or auto-derived), Required for Passport
    gender: Optional[Literal["Male", "Female"]] = Field(
        None, 
        description="Gender - REQUIRED for passport, OPTIONAL for national ID (can be provided manually or auto-derived from ID number)"
    )
    
    place_of_birth: Optional[str] = Field(None, description="Place of birth")
    issuance_date: Optional[str] = Field(None, description="Issuance date (YYYY-MM-DD)")
    expiry_date: Optional[str] = Field(None, description="Expiry date (YYYY-MM-DD)")
    
    @model_validator(mode='after')
    def validate_id_type_fields(self):
        """Ensure appropriate ID number and gender logic based on id_type."""
        if self.id_type == "yemen_national_id":
            if not self.id_number:
                raise ValueError(
                    "id_number is required when id_type is 'yemen_national_id'"
                )
            # Gender is optional for National ID (can be manual or auto-derived)
            # No validation needed here
                
        elif self.id_type == "yemen_passport":
            if not self.passport_number:
                raise ValueError(
                    "passport_number is required when id_type is 'yemen_passport'"
                )
            # Gender MUST be provided for Passport (pre-written on document)
            if not self.gender:
                raise ValueError(
                    "gender is REQUIRED for yemen_passport (it is pre-written on the passport document)"
                )
        
        return self


class IDFormValidationError(BaseModel):
    """Individual validation error detail."""
    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Validation error message")


class IDFormSubmitResponse(BaseModel):
    """Response for ID form submission."""
    success: bool = Field(..., description="Whether validation succeeded")
    message: str = Field(..., description="Success or error message")
    errors: Optional[list[IDFormValidationError]] = Field(
        None,
        description="List of validation errors if validation failed"
    )
    validated_data: Optional[dict] = Field(
        None,
        description="Validated and cleaned form data if successful"
    )

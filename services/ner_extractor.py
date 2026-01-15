"""
Named Entity Recognition (NER) Service for ID Card Data Extraction

Uses spaCy with Arabic NER models to intelligently extract:
- PERSON: Names
- LOC: Addresses/Locations
- DATE: Dates (birth, issuance, expiry)

This is much more accurate than heuristic-based extraction.
"""
import re
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from spacy.language import Language

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: spaCy not installed. NER extraction will be limited.")

from services.translation_service import translate_text


class NERExtractor:
    """NER-based entity extractor for ID card data."""
    
    _instance: Optional["NERExtractor"] = None
    _nlp_ar: Optional["Language"] = None
    _nlp_en: Optional["Language"] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize spaCy models if not already loaded."""
        if not SPACY_AVAILABLE:
            return
            
        if NERExtractor._nlp_ar is None or NERExtractor._nlp_en is None:
            try:
                print("Loading NER models...")
                # Load Arabic model
                try:
                    NERExtractor._nlp_ar = spacy.load("xx_ent_wiki_sm")  # Multilingual model
                    print("  Loaded multilingual NER model (supports Arabic)")
                except OSError:
                    print("  Multilingual model not found. Install with: python -m spacy download xx_ent_wiki_sm")
                    NERExtractor._nlp_ar = None
                
                # Load English model for English text
                try:
                    NERExtractor._nlp_en = spacy.load("en_core_web_sm")
                    print("  Loaded English NER model")
                except OSError:
                    print("  English model not found. Install with: python -m spacy download en_core_web_sm")
                    NERExtractor._nlp_en = None
                    
            except Exception as e:
                print(f"Error loading NER models: {e}")
    
    def extract_entities(self, text: str, lang: str = "ar") -> Dict[str, List[str]]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
            lang: Language code ('ar' or 'en')
            
        Returns:
            Dictionary mapping entity types to lists of entities
        """
        if not SPACY_AVAILABLE:
            return {}
        
        nlp = self._nlp_ar if lang == "ar" else self._nlp_en
        if nlp is None:
            return {}
        
        doc = nlp(text)
        entities = {}
        
        for ent in doc.ents:
            entity_type = ent.label_
            if entity_type not in entities:
                entities[entity_type] = []
            entities[entity_type].append(ent.text)
        
        return entities
    
    def extract_person_names(self, text_results: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract person names using NER.
        
        Args:
            text_results: OCR text results with language detection
            
        Returns:
            Tuple of (arabic_name, english_name)
        """
        arabic_name = None
        english_name = None
        
        # Extract from Arabic texts
        arabic_texts = [
            item['text'] for item in text_results 
            if item.get('detected_language') == 'ar'
        ]
        
        for text in arabic_texts:
            entities = self.extract_entities(text, lang="ar")
            persons = entities.get("PER", []) or entities.get("PERSON", [])
            
            if persons:
                # Take the longest name (usually the full name)
                arabic_name = max(persons, key=len)
                break
        
        # Extract from English texts
        english_texts = [
            item['text'] for item in text_results 
            if item.get('detected_language') == 'en'
        ]
        
        for text in english_texts:
            entities = self.extract_entities(text, lang="en")
            persons = entities.get("PER", []) or entities.get("PERSON", [])
            
            if persons:
                english_name = max(persons, key=len)
                break
        
        # If we have Arabic but not English, translate
        if arabic_name and not english_name:
            english_name = translate_text(arabic_name, source="ar", target="en")
        
        return arabic_name, english_name
    
    def extract_locations(self, text_results: List[Dict]) -> Optional[str]:
        """
        Extract location/address using NER.
        
        Args:
            text_results: OCR text results with language detection
            
        Returns:
            Address in English
        """
        address = None
        
        # Try Arabic texts first
        arabic_texts = [
            item['text'] for item in text_results 
            if item.get('detected_language') == 'ar'
        ]
        
        for text in arabic_texts:
            entities = self.extract_entities(text, lang="ar")
            locations = entities.get("LOC", []) or entities.get("GPE", [])
            
            if locations:
                # Combine all locations
                address = ", ".join(locations)
                # Translate to English
                address = translate_text(address, source="ar", target="en")
                break
        
        # If not found in Arabic, try English
        if not address:
            english_texts = [
                item['text'] for item in text_results 
                if item.get('detected_language') == 'en'
            ]
            
            for text in english_texts:
                entities = self.extract_entities(text, lang="en")
                locations = entities.get("LOC", []) or entities.get("GPE", [])
                
                if locations:
                    address = ", ".join(locations)
                    break
        
        return address
    
    def extract_dates_with_ner(self, text_results: List[Dict]) -> List[str]:
        """
        Extract dates using NER.
        
        Args:
            text_results: OCR text results
            
        Returns:
            List of extracted dates in YYYY-MM-DD format
        """
        dates = []
        
        all_texts = [item['text'] for item in text_results]
        
        for text in all_texts:
            # Try with both models
            for lang in ["ar", "en"]:
                entities = self.extract_entities(text, lang=lang)
                date_entities = entities.get("DATE", [])
                
                for date_str in date_entities:
                    # Try to parse and format the date
                    parsed_date = self._parse_date_string(date_str)
                    if parsed_date:
                        dates.append(parsed_date)
        
        return dates
    
    def _parse_date_string(self, date_str: str) -> Optional[str]:
        """
        Parse a date string and return in YYYY-MM-DD format.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Formatted date or None
        """
        # Common date patterns
        patterns = [
            (r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', "YMD"),
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', "DMY"),
            (r'(\d{4})(\d{2})(\d{2})', "YMD"),
        ]
        
        for pattern, order in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if order == "YMD":
                        year, month, day = match.groups()
                    else:  # DMY
                        day, month, year = match.groups()
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    return date_obj.strftime("%Y-%m-%d")
                except (ValueError, IndexError):
                    continue
        
        return None


# Singleton instance
_ner_extractor: Optional[NERExtractor] = None


def get_ner_extractor() -> NERExtractor:
    """Get the singleton NER extractor instance."""
    global _ner_extractor
    if _ner_extractor is None:
        _ner_extractor = NERExtractor()
    return _ner_extractor


def is_ner_available() -> bool:
    """Check if NER functionality is available."""
    return SPACY_AVAILABLE and (
        NERExtractor._nlp_ar is not None or 
        NERExtractor._nlp_en is not None
    )

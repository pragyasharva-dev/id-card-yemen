"""
PDF Image Extractor for ID Cards
Extracts front ID, back ID, and selfie images from PDF files.
"""
import fitz  # PyMuPDF
import os
from pathlib import Path
from PIL import Image
import io


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> dict:
    """
    Extract images from a PDF file containing ID card front and back.
    - 2nd page (index 1) = front ID → saved to front_side folder
    - 3rd page (index 2) = back ID → saved to back_side folder
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Base output directory for extracted images
        
    Returns:
        Dictionary with paths to extracted images
    """
    pdf_name = Path(pdf_path).stem  # Get filename without extension
    
    # Create output folders
    front_dir = os.path.join(output_dir, "front_side")
    back_dir = os.path.join(output_dir, "back_side")
    os.makedirs(front_dir, exist_ok=True)
    os.makedirs(back_dir, exist_ok=True)
    
    result = {"front": None, "back": None}
    
    # Map pages to image types and folders (0-indexed)
    page_mapping = {
        1: ("front", front_dir),   # 2nd page = front ID
        2: ("back", back_dir),     # 3rd page = back ID
    }
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            if page_num not in page_mapping:
                continue
                
            img_type, img_dir = page_mapping[page_num]
            images = page.get_images()
            
            if images:
                # Get the largest image on the page (skip small icons)
                best_image = None
                best_size = 0
                
                for img in images:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    size = base_image["width"] * base_image["height"]
                    
                    if size > best_size:
                        best_size = size
                        best_image = base_image
                
                if best_image:
                    # Convert to PIL Image and save as JPEG
                    img_data = best_image["image"]
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    # Convert to RGB if necessary
                    if pil_image.mode in ('RGBA', 'P'):
                        pil_image = pil_image.convert('RGB')
                    
                    # Save image with PDF name
                    output_path = os.path.join(img_dir, f"{pdf_name}.jpg")
                    pil_image.save(output_path, "JPEG", quality=95)
                    result[img_type] = output_path
                    
        doc.close()
        
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        
    return result


def process_all_pdfs(pdf_folder: str, output_folder: str):
    """
    Process all PDF files in a folder.
    
    Args:
        pdf_folder: Folder containing PDF files
        output_folder: Folder to save extracted images
    """
    pdf_files = list(Path(pdf_folder).glob("*.pdf"))
    total = len(pdf_files)
    
    print(f"Found {total} PDF files to process")
    print(f"Output folder: {output_folder}")
    print("-" * 50)
    
    success_count = 0
    error_count = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{total}] Processing: {pdf_path.name}")
        
        result = extract_images_from_pdf(str(pdf_path), output_folder)
        
        if result["front"] and result["back"]:
            success_count += 1
        else:
            error_count += 1
            missing = [k for k, v in result.items() if v is None]
            print(f"  Warning: Missing images: {missing}")
    
    print("-" * 50)
    print(f"Processing complete!")
    print(f"  Success: {success_count}/{total}")
    print(f"  Errors/Warnings: {error_count}")
    print(f"\nImages saved to:")
    print(f"  Front IDs: {os.path.join(output_folder, 'front_side')}")
    print(f"  Back IDs: {os.path.join(output_folder, 'back_side')}")


if __name__ == "__main__":
    # Source and destination folders
    PDF_FOLDER = r"C:\Users\Admin\Desktop\One_Cash\OneCash_400img"
    OUTPUT_FOLDER = r"d:\id-card-yemen\data\extracted_images"
    
    process_all_pdfs(PDF_FOLDER, OUTPUT_FOLDER)

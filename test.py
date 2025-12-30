import os
import cv2
import numpy as np
from paddleocr import PaddleOCR

os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"


def preprocess_image(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not read image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)

    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


def extract_text_from_result(result):
    extracted = []

    # ✅ PaddleOCR returns LIST of dicts
    if isinstance(result, list) and len(result) > 0:
        res = result[0]

        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])

        for i, text in enumerate(texts):
            text = text.strip()
            if not text:
                continue

            if i < len(scores):
                extracted.append(f"{text} (conf: {scores[i]:.2f})")
            else:
                extracted.append(text)

    return extracted


def ocr_image_to_text_file(image_path: str, output_txt="ocr_output.txt"):
    ocr = PaddleOCR(
        lang="ar",
        use_textline_orientation=True
    )

    img = preprocess_image(image_path)

    # ✅ predict(), not ocr()
    result = ocr.predict(img)

    extracted = extract_text_from_result(result)

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(extracted))

    print("OCR complete.")
    print("Lines extracted:", len(extracted))
    print("Output written to:", output_txt)


if __name__ == "__main__":
    ocr_image_to_text_file("retrieve (1).png")

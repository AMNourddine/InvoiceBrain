import os, sys, json, shutil, datetime, uuid
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageFile

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Folders
INCOMING = "incoming"
PO_OUT = "data/PO_detected"
RO_OUT = "data/RO_detected"
PROCESSED = "data/processed"

os.makedirs(PO_OUT, exist_ok=True)
os.makedirs(RO_OUT, exist_ok=True)
os.makedirs(PROCESSED, exist_ok=True)

def detect_type(pdf):
    # Convert first page
    pages = convert_from_path(pdf, dpi=200, first_page=1, last_page=1)
    img = np.array(pages[0])
    h, w = img.shape[:2]

    # Crop top-left area for title
    y1, y2 = int(h * 0.1), int(h * 0.30)
    x1, x2 = 0, int(w * 0.72)
    crop = img[y1:y2, x1:x2]

    # Enhance for OCR
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # OCR
    text = pytesseract.image_to_string(th, lang="fra+eng").upper()

    # Detect type
    if "BON DE COMMANDE" in text:
        doc = "PO"
    elif "BON DE RECEPTION" in text:
        doc = "RO"
    else:
        doc = "UNKNOWN"

    today = datetime.datetime.now().strftime("%Y%m%d")
    uid = str(uuid.uuid4())[:8]
    newname = f"{doc}-{today}-{uid}.pdf"

    # Always move original to processed folder
    processed_path = os.path.join(PROCESSED, newname)
    shutil.move(pdf, processed_path)

    # Create a copy in corresponding folder for extraction
    if doc == "PO":
        dest = os.path.join(PO_OUT, newname)
        shutil.copy(processed_path, dest)
    elif doc == "RO":
        dest = os.path.join(RO_OUT, newname)
        shutil.copy(processed_path, dest)
    else:
        dest = processed_path  # keep unknowns only in processed

    return {"path": dest, "type": doc}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ No PDF path provided")
        sys.exit(1)

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(f"❌ PDF not found: {pdf}")
        sys.exit(1)

    info = detect_type(pdf)
    print(json.dumps(info, ensure_ascii=False))

# RO_Header_Crop.py
import sys, os, cv2, pytesseract, json, re
import numpy as np
from pdf2image import convert_from_path
from PIL import Image, ImageFile

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.join(BASE, "debug")
os.makedirs(DEBUG, exist_ok=True)

# === Input PDF ===
if len(sys.argv) < 2:
    print("❌ No PDF path provided")
    sys.exit(1)

pdf = sys.argv[1]
pages = convert_from_path(pdf, dpi=300, first_page=1, last_page=1)
img = np.array(pages[0])
h, w = img.shape[:2]

# === Crop header area ===
y1, y2 = int(h * 0.1), int(h * 0.29)
x1, x2 = int(w * 0.0), int(w * 0.60)
crop = img[y1:y2, x1:x2]
cv2.imwrite(os.path.join(DEBUG, "ro_header_raw.png"), crop)

# === Preprocess ===
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
gray = cv2.fastNlMeansDenoising(gray, h=20)
gray = cv2.bilateralFilter(gray, 7, 75, 75)
gray = cv2.convertScaleAbs(gray, alpha=1.7, beta=0)
_, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
th = cv2.bitwise_not(th)
cv2.imwrite(os.path.join(DEBUG, "ro_header_clean.png"), th)

# === OCR ===
text = pytesseract.image_to_string(th, lang="fra+eng")
text_u = text.upper()
with open(os.path.join(DEBUG, "ro_header_text.txt"), "w", encoding="utf-8") as f:
    f.write(text_u)

# Normalize spacing
text_u = re.sub(r"\s+", " ", text_u)

# === Extract fields ===

# 📅 Date
date = None
dm = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text_u)
if dm:
    date = dm.group(1)
    dd, mm, yy = date.split("/")
    date_norm = f"{yy}{mm}{dd}"
else:
    date_norm = None

# 🔍 Reception number (DAC)
reception_number = None
dac = re.search(r"DAC\s*[/\-]?\s*(\d{5,15})", text_u)
if dac:
    reception_number = f"DAC{dac.group(1)}"

# 🔍 Order number (N° Commande)
# Fallback: look for a long standalone number after DAC/date
order_number = None
if not order_number:
    # find all long numeric blocks
    nums = re.findall(r"\b\d{6,12}\b", text_u)
    # DAC digits (if any)
    dac_digits = re.sub(r"\D", "", reception_number) if reception_number else None
    # pick number that isn't DAC and isn't part of the date
    for n in nums:
        if dac_digits and n == dac_digits:
            continue
        if date and n in date.replace("/", ""):
            continue
        order_number = n
        break

# === Output JSON ===
print(json.dumps({
    "document_type": "RO",
    "date": date,
    "date_norm": date_norm,
    "reception_number": reception_number,  # N° Réception
    "order_number": order_number           # N° Commande
}, ensure_ascii=False))

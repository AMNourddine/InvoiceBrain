import os, re
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image, ImageFile
import pytesseract
import json

import sys, os
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ✅ Accept file path argument from InvoiceBrain
if len(sys.argv) < 2:
    print("❌ No PDF path provided")
    sys.exit(1)

PDF_PATH = sys.argv[1]

if not os.path.exists(PDF_PATH):
    print(f"❌ PDF not found: {PDF_PATH}")
    sys.exit(1)


os.makedirs("debug", exist_ok=True)

# Convert PDF → last page
pages = convert_from_path(PDF_PATH, dpi=300)
page = np.array(pages[-1])
h, w = page.shape[:2]

# Crop bottom-right area (big safe crop)
y1 = int(h * 0.70)
y2 = int(h * 0.80)
x1 = int(w * 0.70)
x2 = int(w * 1.00)

crop = page[y1:y2, x1:x2]
cv2.imwrite("debug/area_totals.png", crop)

# Enhance for OCR
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
gray = cv2.bilateralFilter(gray, 7, 75, 75)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
cv2.imwrite("debug/area_totals_thresh.png", thresh)

# OCR text
raw = pytesseract.image_to_string(
    thresh,
    lang="fra+eng",
    config="--psm 6"
)

text = raw.replace("\n", " ")

print("\n=== OCR TEXT ===")
print(text)

import re

def normalize_number(v):
    if not v:
        return None
    v = v.replace(" ", "").replace(",", ".")
    v = re.sub(r"[^0-9.]", "", v)
    try:
        return float(v)
    except:
        return None

def find_label_value(label, text):
    pattern = rf"{label}\s+([\d\s.,]+)"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return normalize_number(m.group(1))

def extract_totals(text):
    # Try direct label extraction
    ht  = find_label_value(r"Total HT", text)
    tax = find_label_value(r"Total Taxe|Taxe|TVA", text)
    ttc = find_label_value(r"Total TTC|TTC", text)

    # Fallback: find top numeric values
    nums = re.findall(r"\d[\d\s.,]*\d", text)
    clean = sorted({normalize_number(n) for n in nums if normalize_number(n)},
                   reverse=True)

    # TTC is always largest
    if ttc is None and clean:
        ttc = clean[0]

    # HT is second largest (if missing)
    if ht is None and len(clean) > 1:
        ht = clean[1]

    # Tax is third largest (if missing)
    if tax is None and len(clean) > 2:
        tax = clean[2]

    return ht, tax, ttc

# Test
if __name__ == "__main__":
    ht, tax, ttc = extract_totals(text)

    print("\n=== FINAL TOTALS ===")
    print("Total HT :", ht)
    print("Total Taxe:", tax)
    print("Total TTC:", ttc)
    print("====================")


result = {
    "total_ht": ht,
    "total_tax": tax,
    "total_ttc": ttc
}

print(json.dumps(result))





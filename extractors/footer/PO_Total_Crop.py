import os, re, cv2, sys, json
import numpy as np
from pdf2image import convert_from_path
from PIL import Image, ImageFile
import pytesseract

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

if len(sys.argv) < 2:
    print("❌ No PDF path provided")
    sys.exit(1)

PDF_PATH = sys.argv[1]
if not os.path.exists(PDF_PATH):
    print(f"❌ PDF not found: {PDF_PATH}")
    sys.exit(1)

BASE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.join(BASE, "debug")
os.makedirs(DEBUG, exist_ok=True)




# Convert PDF → last page
pages = convert_from_path(PDF_PATH, dpi=300)
page = np.array(pages[-1])
h, w = page.shape[:2]

# 🔧 Slightly bigger crop area
y1 = int(h * 0.70)
y2 = int(h * 0.78)
x1 = int(w * 0.60)
x2 = int(w * 0.98)
crop = page[y1:y2, x1:x2]
cv2.imwrite(os.path.join(DEBUG, "po_footer_raw.png"), crop)

# Preprocess for OCR
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
gray = cv2.convertScaleAbs(gray, alpha=1.7, beta=0)
gray = cv2.bilateralFilter(gray, 7, 75, 75)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
cv2.imwrite(os.path.join(DEBUG, "po_footer_clean.png"), thresh)

# OCR
raw = pytesseract.image_to_string(thresh, lang="fra+eng", config="--psm 6")
text = raw.replace("\n", " ")

# Save OCR output
with open(os.path.join(DEBUG, "po_footer_text.txt"), "w", encoding="utf-8") as f:
    f.write(text)

print("\n=== OCR TEXT (PO) ===")
print(text)

# -----------------------------
# Extraction helpers
# -----------------------------
def normalize_number(v):
    if not v: return None
    v = v.replace(" ", "").replace(",", ".")
    v = re.sub(r"[^0-9.]", "", v)
    try:
        return float(v)
    except:
        return None

def find_label_value(label, text):
    pattern = rf"{label}\s*[:\-]?\s*([\d\s.,]+)"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return normalize_number(m.group(1))

def extract_totals(text):
    # Try all possible label variants
    ht  = find_label_value(r"(Total HT|Montant HT|HT)", text)
    tax = find_label_value(r"(TVA|Taxe|Total Taxe|Montant Taxe)", text)
    ttc = find_label_value(r"(Total TTC|TTC|Montant TTC)", text)

    nums = re.findall(r"\d[\d\s.,]*\d", text)
    clean = sorted({normalize_number(n) for n in nums if normalize_number(n)}, reverse=True)

    if ttc is None and clean: ttc = clean[0]
    if ht is None and len(clean) > 1: ht = clean[1]
    if tax is None and len(clean) > 2: tax = clean[2]

    return ht, tax, ttc

# Run extraction
ht, tax, ttc = extract_totals(text)

print("\n=== FINAL TOTALS (PO) ===")
print("Total HT :", ht)
print("Total Taxe:", tax)
print("Total TTC:", ttc)
print("====================")

result = {"total_ht": ht, "total_tax": tax, "total_ttc": ttc}
print(json.dumps(result))

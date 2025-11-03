import os, re, sys, json, cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image, ImageFile
import pytesseract

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# === Input check ===
if len(sys.argv) < 2:
    print("❌ No PDF path provided")
    sys.exit(1)

PDF_PATH = sys.argv[1]
if not os.path.exists(PDF_PATH):
    print(f"❌ PDF not found: {PDF_PATH}")
    sys.exit(1)

# === Setup debug folder ===
BASE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.join(BASE, "debug")
os.makedirs(DEBUG, exist_ok=True)

# === Convert PDF → last page image ===
pages = convert_from_path(PDF_PATH, dpi=300)
page = np.array(pages[-1])
h, w = page.shape[:2]

# === Crop bottom-right area (adjust if needed) ===
y1 = int(h * 0.78)
y2 = int(h * 0.90)
x1 = int(w * 0.55)
x2 = int(w * 0.98)
crop = page[y1:y2, x1:x2]
cv2.imwrite(os.path.join(DEBUG, "ro_footer_raw.png"), crop)

# === Preprocess for OCR ===
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# Enhance contrast and denoise
gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)
gray = cv2.fastNlMeansDenoising(gray, h=20)

# Adaptive threshold for thin fonts
thresh = cv2.adaptiveThreshold(gray, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 8)

# Morphological dilation to bolden thin digits
kernel = np.ones((2, 2), np.uint8)
dilated = cv2.dilate(thresh, kernel, iterations=1)

# Invert back (black text on white)
final = cv2.bitwise_not(dilated)
cv2.imwrite(os.path.join(DEBUG, "ro_footer_clean.png"), final)

# === OCR ===
raw = pytesseract.image_to_string(
    final, lang="fra+eng", config="--psm 6"
)
text = raw.replace("\n", " ").replace("—", "-").replace(";", ":")

with open(os.path.join(DEBUG, "ro_footer_text.txt"), "w", encoding="utf-8") as f:
    f.write(text)

print("\n=== OCR TEXT (RO) ===")
print(text)

# === Extraction helpers ===
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
    pattern = rf"{label}\s*[:\-]?\s*([\d\s.,]+)"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return normalize_number(m.group(1))

def extract_totals(text):
    ht  = find_label_value(r"(Total HT|Montant HT|HT)", text)
    tax = find_label_value(r"(Total Taxe|Taxe|TVA|Montant Taxe)", text)
    ttc = find_label_value(r"(Total TTC|TTC|Montant TTC)", text)

    # Fallback: pick biggest numbers if labels fail
    nums = re.findall(r"\d[\d\s.,]*\d", text)
    clean = sorted({normalize_number(n) for n in nums if normalize_number(n)}, reverse=True)

    if ttc is None and clean:
        ttc = clean[0]
    if ht is None and len(clean) > 1:
        ht = clean[1]
    if tax is None and len(clean) > 2:
        tax = clean[2]

    return ht, tax, ttc

# === Run extraction ===
ht, tax, ttc = extract_totals(text)

print("\n=== FINAL TOTALS (RO) ===")
print("Total HT :", ht)
print("Total Taxe:", tax)
print("Total TTC:", ttc)
print("====================")

# === Final JSON output ===
result = {
    "total_ht": ht,
    "total_tax": tax,
    "total_ttc": ttc
}
print(json.dumps(result, ensure_ascii=False))

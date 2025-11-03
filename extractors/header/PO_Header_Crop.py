# PO_Header_Crop.py
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

# === Crop header area (works for your PDFs) ===
y1, y2 = int(h * 0.15), int(h * 0.30)
x1, x2 = 0, int(w * 0.60)
crop = img[y1:y2, x1:x2]
cv2.imwrite(os.path.join(DEBUG, "po_header_raw.png"), crop)

# === Preprocess ===
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# Step 1: gamma correction (boost dark ink)
gamma = 0.6
invGamma = 1.0 / gamma
table = np.array([(i / 255.0) ** invGamma * 255 for i in np.arange(256)]).astype("uint8")
gray = cv2.LUT(gray, table)

# Step 2: CLAHE for local contrast
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
gray = clahe.apply(gray)

# Step 3: remove smooth background using morphological opening
bg = cv2.morphologyEx(gray, cv2.MORPH_OPEN,
                      cv2.getStructuringElement(cv2.MORPH_RECT, (25,25)))
norm = cv2.subtract(gray, bg)
norm = cv2.normalize(norm, None, 0, 255, cv2.NORM_MINMAX)

# Step 4: threshold with Otsu
_, th = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

# Step 5: invert (black text on white)
final = cv2.bitwise_not(th)

cv2.imwrite(os.path.join(DEBUG, "po_header_clean.png"), final)

# === OCR ===
text = pytesseract.image_to_string(
    final,
    lang="fra+eng",
    config="--psm 6 --oem 3 -c preserve_interword_spaces=1"
)
text_u = text.upper()
with open(os.path.join(DEBUG, "po_header_text.txt"), "w", encoding="utf-8") as f:
    f.write(text_u)

# === Normalize spacing and fix OCR typos ===
text_u = re.sub(r"\s+", " ", text_u)
for wrong, right in {
    "FORTIS DIE": "FOURNISSEUR",
    "FOURNI SSEUR": "FOURNISSEUR",
}.items():
    text_u = text_u.replace(wrong, right)

# === Extract fields ===
# Date
dm = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text_u)
date = dm.group(1) if dm else None
date_norm = f"{date[6:]}{date[3:5]}{date[:2]}" if date else None

# PO reference
po = re.search(r"DAC\s*[/\-]?\s*(\d{5,15})", text_u)
po_reference = f"DAC{po.group(1)}" if po else None

# Supplier code
supp_match = re.search(r"CODE\s*FOURNI[SS]EUR\s*[:\-=]?\s*(\d{4,10})", text_u)
if supp_match:
    supplier_code = supp_match.group(1)
else:
    nums = re.findall(r"\b\d{6,10}\b", text_u)
    supplier_code = nums[-1] if nums else None

# === Output JSON ===
print(json.dumps({
    "document_type": "PO",
    "date": date,
    "date_norm": date_norm,
    "po_reference": po_reference,
    "supplier_code": supplier_code
}, ensure_ascii=False))

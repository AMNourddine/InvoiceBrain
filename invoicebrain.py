import os, re, shutil, sys, json
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageFile
import subprocess

# Allow large PDF images
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Paths
processed_dir = "data/processed"
po_dir = "data/purchase_orders"
ro_dir = "data/reception_orders"
debug_dir = "debug"

os.makedirs(processed_dir, exist_ok=True)
os.makedirs(po_dir, exist_ok=True)
os.makedirs(ro_dir, exist_ok=True)
os.makedirs(debug_dir, exist_ok=True)

def normalize_dac(val):
    val = val.replace(" ", "")
    return re.sub(r"[^A-Za-z0-9]", "", val)

def extract_fields(pdf_path):
    pages = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=1)
    img = np.array(pages[0])
    h, w = img.shape[:2]

    # Crop ROI for header
    y1, y2 = int(h * 0.131), int(h * 0.29)
    x1, x2 = 0, int(w * 0.60)
    crop = img[y1:y2, x1:x2]
    cv2.imwrite(f"{debug_dir}/crop_region.png", crop)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite(f"{debug_dir}/header_clean.png", thresh)

    text = " ".join(pytesseract.image_to_string(thresh, lang="fra+eng").split())
    text_u = text.upper()

    print("\n===== RAW OCR CLEANED =====")
    print(text)

    # Detect PO vs RO
    if "BON DE RECEPTION" in text_u:
        doc_type = "RO"
    elif "BON DE COMMANDE" in text_u:
        doc_type = "PO"
    else:
        doc_type = "UNKNOWN"

    print(f"\n📄 document_type: {doc_type}")

    # Extract date
    dm = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    date = dm.group(1) if dm else None
    date_norm = None
    if date:
        dd, mm, yy = date.split("/")
        date_norm = f"{yy}{mm}{dd}"

    # DAC ref
    # ✅ Capture DAC number even if followed by quantity like "DAC/250000013 3"
    m = re.search(r"(DAC\s*/\s*(\d{6,12}))", text, re.IGNORECASE)

    if m:
        dac_digits = re.sub(r"[^0-9]", "", m.group(2))  # only the number part
        dac_ref = f"DAC{dac_digits}"
    else:
        dac_ref = None



    # Command number
    command_number = None
    nums = re.findall(r"\b\d{8,12}\b", text)

    if doc_type == "RO" and dac_ref:
        dac_num = re.sub(r"\D", "", dac_ref)
        for n in nums:
            if n != dac_num:
                command_number = n
                break
    elif doc_type == "PO":
        command_number = re.sub(r"\D", "", dac_ref) if dac_ref else None

    return {
        "document_type": doc_type,
        "date": date,
        "date_norm": date_norm,
        "po_reference": dac_ref if doc_type == "PO" else None,
        "ro_reference": dac_ref if doc_type == "RO" else None,
        "command_number": command_number
    }

def save_txt(fields, base_path):
    txt_path = base_path + ".txt"
    with open(txt_path, "w") as f:
        for k, v in fields.items():
            f.write(f"{k}:{v}\n")
    print(f"📝 Metadata saved: {txt_path}")

def rename_and_store(pdf_path, fields):
    doc_type = fields["document_type"]
    if doc_type == "UNKNOWN":
        print("⚠️ Unknown doc → skip.")
        return None

    date = fields["date_norm"]
    dac = fields["po_reference"] if doc_type == "PO" else fields["ro_reference"]

    if not date or not dac:
        print("⚠️ Missing date or reference, skip.")
        return None

    new_name = f"{doc_type}-{date}-{dac}"
    new_pdf = new_name + ".pdf"

    out_dir = po_dir if doc_type == "PO" else ro_dir
    dest_pdf = os.path.join(out_dir, new_pdf)

    shutil.copy2(pdf_path, dest_pdf)
    shutil.move(pdf_path, os.path.join(processed_dir, os.path.basename(pdf_path)))
    print(f"✅ Renamed to {new_pdf}")
    print(f"📂 Stored in {out_dir}")

    base = os.path.join(out_dir, new_name)
    save_txt(fields, base)

    return dest_pdf  # return new path for next script

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 invoicebrain.py file.pdf")
        sys.exit()

    original_pdf = sys.argv[1]

    fields = extract_fields(original_pdf)
    new_pdf = rename_and_store(original_pdf, fields)

    if not new_pdf:
        sys.exit()

    doc_type = fields["document_type"]
    
    # Run totals script automatically
    # ✨ Run totals extraction and capture JSON output
    if doc_type == "PO":
        print("📊 Running PO totals extractor...")
        output = subprocess.check_output(["python3", "PO_Total_Crop.py", new_pdf]).decode()
    elif doc_type == "RO":
        print("📊 Running RO totals extractor...")
        output = subprocess.check_output(["python3", "RO_Total_Crop.py", new_pdf]).decode()
    else:
        output = None

    # ✨ Parse totals JSON & append to txt file
    if output:
        try:
            last_line = output.strip().split("\n")[-1]
            totals = json.loads(last_line)

            txt_path = new_pdf.replace(".pdf", ".txt")  # same name as metadata txt

            with open(txt_path, "a") as f:
                f.write(f"total_ht:{totals.get('total_ht')}\n")
                f.write(f"total_tax:{totals.get('total_tax')}\n")
                f.write(f"total_ttc:{totals.get('total_ttc')}\n")

            print(f"🧾 Totals appended to {txt_path}")

        except Exception as e:
            print("⚠️ Warning: Could not parse totals response")
            print("Response was:", output)
            print("Error →", e)

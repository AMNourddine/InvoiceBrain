import sys, json, subprocess, os, csv

BASE = os.path.dirname(os.path.abspath(__file__))
HEADER = os.path.join(BASE, "header", "PO_Header_Crop.py")
FOOTER = os.path.join(BASE, "footer", "PO_Total_Crop.py")


def safe_json_output(cmd):
    """Return last valid JSON line emitted by the subprocess, or {}."""
    out = subprocess.check_output(cmd, text=True).splitlines()
    for line in reversed(out):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def extract_PO_data(pdf_path: str):
    header = safe_json_output(["python3", HEADER, pdf_path])
    footer = safe_json_output(["python3", FOOTER, pdf_path])

    data = {**header, **footer}

    # Normalize field names
    if "po_reference" in data:
        data["order_number"] = data.pop("po_reference")
    if "command_number" in data:
        data["supplier_code"] = data.pop("command_number")

    keys = [
        "document_type",
        "date",
        "date_norm",
        "order_number",
        "supplier_code",
        "total_ht",
        "total_tax",
        "total_ttc",
    ]
    clean = {k: data.get(k) for k in keys if data.get(k)}

    name = os.path.splitext(os.path.basename(pdf_path))[0]
    csv_path = os.path.join(os.path.dirname(pdf_path), f"{name}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["field", "value"])
        for k, v in clean.items():
            w.writerow([k, v])

    print(json.dumps(clean, ensure_ascii=False))
    print("✅ CSV saved:", csv_path)
    return clean


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ No PDF path provided")
        sys.exit(1)

    extract_PO_data(sys.argv[1])

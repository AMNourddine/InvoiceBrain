#!/usr/bin/env python3
import json, sys, os

PROCESSED_DIR = os.path.join("data", "processed")


def choose_target_stem(base_stem: str, old_stem: str, base_dir: str):
    """Return target stem and whether a rename is required."""
    def already_normalized(stem: str) -> bool:
        return stem == base_stem or stem.startswith(f"{base_stem}-")

    if already_normalized(old_stem):
        return old_stem, False

    suffix = 1
    while True:
        suffix_part = "" if suffix == 1 else f"-{suffix}"
        candidate_stem = f"{base_stem}{suffix_part}"
        candidate_pdf = os.path.join(base_dir, f"{candidate_stem}.pdf")
        candidate_csv = os.path.join(base_dir, f"{candidate_stem}.csv")
        candidate_processed = os.path.join(PROCESSED_DIR, f"{candidate_stem}.pdf")

        if not (
            os.path.exists(candidate_pdf)
            or os.path.exists(candidate_csv)
            or os.path.exists(candidate_processed)
        ):
            return candidate_stem, True

        suffix += 1

# === Input from detect_type.py ===
if len(sys.argv) < 2:
    print("❌ No JSON input provided")
    sys.exit(1)

meta = json.loads(sys.argv[1])
pdf_path = meta.get("path")
doc_type = meta.get("type")

if not pdf_path or not os.path.exists(pdf_path):
    print(f"❌ PDF not found: {pdf_path}")
    sys.exit(1)

print(f"📄 Processing: {pdf_path} ({doc_type})")

# === Run extraction according to type ===
if doc_type == "PO":
    from extractors.PO_final_extractor import extract_PO_data
    output = extract_PO_data(pdf_path)
elif doc_type == "RO":
    from extractors.RO_final_extractor import extract_RO_data
    output = extract_RO_data(pdf_path)
else:
    print(f"⚠️ Unknown document type: {doc_type}")
    sys.exit(1)

# === Save CSV (already handled inside your extractors) ===
print(json.dumps(output, ensure_ascii=False, indent=2))

# === Rename after extraction ===
date_norm = output.get("date_norm")
order_number = output.get("order_number")

reception_number = output.get("reception_number")

if doc_type == "PO" and date_norm and order_number:
    base_dir = os.path.dirname(pdf_path)
    old_name = os.path.basename(pdf_path)
    old_stem = os.path.splitext(old_name)[0]
    base_stem = f"{doc_type}-{date_norm}-{order_number}"
    target_stem, needs_rename = choose_target_stem(base_stem, old_stem, base_dir)
    target_name = f"{target_stem}.pdf"

    if needs_rename:
        target_path = os.path.join(base_dir, target_name)
        os.rename(pdf_path, target_path)
        print(f"✅ Renamed extraction copy → {target_name}")
        pdf_path = target_path

        csv_old = os.path.join(base_dir, f"{old_stem}.csv")
        csv_new = os.path.join(base_dir, f"{target_stem}.csv")

        if os.path.exists(csv_old):
            if not os.path.exists(csv_new):
                os.rename(csv_old, csv_new)
                print(f"✅ Renamed CSV → {os.path.basename(csv_new)}")
            else:
                print(f"⚠️ CSV with name {os.path.basename(csv_new)} already exists. Skipping rename.")
        elif not os.path.exists(csv_new):
            print("⚠️ Could not rename CSV: original file not found.")
    else:
        print(f"ℹ️ Extraction copy already normalized as {target_name}.")

    processed_old = os.path.join(PROCESSED_DIR, old_name)
    processed_new = os.path.join(PROCESSED_DIR, f"{target_stem}.pdf")

    if processed_old != processed_new:
        if os.path.exists(processed_old):
            if not os.path.exists(processed_new):
                os.rename(processed_old, processed_new)
                print(f"✅ Renamed processed copy → {os.path.basename(processed_new)}")
            else:
                print(f"⚠️ Processed copy with name {os.path.basename(processed_new)} already exists. Skipping rename.")
        elif not os.path.exists(processed_new):
            print("⚠️ Could not rename processed copy: original file not found.")
elif doc_type == "RO" and date_norm and reception_number:
    base_dir = os.path.dirname(pdf_path)
    old_name = os.path.basename(pdf_path)
    old_stem = os.path.splitext(old_name)[0]
    base_stem = f"{doc_type}-{date_norm}-{reception_number}"
    target_stem, needs_rename = choose_target_stem(base_stem, old_stem, base_dir)
    target_name = f"{target_stem}.pdf"

    if needs_rename:
        target_path = os.path.join(base_dir, target_name)
        os.rename(pdf_path, target_path)
        print(f"✅ Renamed extraction copy → {target_name}")
        pdf_path = target_path

        csv_old = os.path.join(base_dir, f"{old_stem}.csv")
        csv_new = os.path.join(base_dir, f"{target_stem}.csv")

        if os.path.exists(csv_old):
            if not os.path.exists(csv_new):
                os.rename(csv_old, csv_new)
                print(f"✅ Renamed CSV → {os.path.basename(csv_new)}")
            else:
                print(f"⚠️ CSV with name {os.path.basename(csv_new)} already exists. Skipping rename.")
        elif not os.path.exists(csv_new):
            print("⚠️ Could not rename CSV: original file not found.")
    else:
        print(f"ℹ️ Extraction copy already normalized as {target_name}.")

    processed_old = os.path.join(PROCESSED_DIR, old_name)
    processed_new = os.path.join(PROCESSED_DIR, f"{target_stem}.pdf")

    if processed_old != processed_new:
        if os.path.exists(processed_old):
            if not os.path.exists(processed_new):
                os.rename(processed_old, processed_new)
                print(f"✅ Renamed processed copy → {os.path.basename(processed_new)}")
            else:
                print(f"⚠️ Processed copy with name {os.path.basename(processed_new)} already exists. Skipping rename.")
        elif not os.path.exists(processed_new):
            print("⚠️ Could not rename processed copy: original file not found.")
else:
    if doc_type == "PO":
        print("⚠️ Could not rename: missing date_norm or order_number.")
    elif doc_type == "RO":
        print("⚠️ Could not rename: missing date_norm or reception_number.")
    else:
        print("⚠️ Skipping rename for unsupported document type.")

print(f"🏁 Final file: {pdf_path}")

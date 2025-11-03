#!/usr/bin/env python3
import os
import time
import subprocess
from datetime import datetime

INCOMING_DIR = "incoming"
PROCESSED_DIR = "data/processed"
SLEEP_INTERVAL = 5  # seconds between directory checks

os.makedirs(INCOMING_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def process_new_pdf(pdf_path: str):
    """Run the full classification + processing pipeline on one PDF."""
    print(f"📄 New file detected: {pdf_path}")

    # 1️⃣ Run detect_type.py
    try:
        print("🤖 Detecting document type...")
        result = subprocess.run(
            ["python3", "detect_type.py", pdf_path],
            capture_output=True, text=True, check=True
        )
        print("📄 detect_type.py output:\n", result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"❌ detect_type.py failed for {pdf_path}")
        print(e.stderr)
        return

    # 2️⃣ Run process_doc.py
    try:
        print("⚙️ Processing document...")
        subprocess.run(
            ["python3", "process_doc.py", result.stdout.strip()],
            check=True
        )

    except subprocess.CalledProcessError as e:
        print(f"❌ process_doc.py failed for {pdf_path}")
        print(e.stderr)
        return

    # 3️⃣ Mark completion (file already moved by detect_type.py)
    print("✅ Processing completed successfully!")
    print("   (Original PDF already relocated by detect_type.py)")


def main():
    print(f"👀 Watching folder: {INCOMING_DIR}")
    seen: set[str] = set()

    # Process any PDFs already present before watching for new ones.
    existing_files = sorted(
        f for f in os.listdir(INCOMING_DIR) if f.lower().endswith(".pdf")
    )
    for filename in existing_files:
        pdf_path = os.path.join(INCOMING_DIR, filename)
        process_new_pdf(pdf_path)

    seen.update(existing_files)

    while True:
        time.sleep(SLEEP_INTERVAL)
        current_files = set(f for f in os.listdir(INCOMING_DIR) if f.lower().endswith(".pdf"))
        new_files = sorted(current_files - seen)
        for filename in new_files:
            pdf_path = os.path.join(INCOMING_DIR, filename)
            process_new_pdf(pdf_path)
        seen = current_files

if __name__ == "__main__":
    main()

import pytesseract
import cv2
import numpy as np
import mss
import time
import re

sct = mss.mss()

# Set your Tesseract install path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === REGION: Your First Card ===
# Using top-left coordinates from you: (1829, 946)
# We'll assume ~40px right and ~40px down to start
card_1_region = (1829, 946, 1870, 986)

def grab_gray(region):
    monitor = {
        "top": region[1],
        "left": region[0],
        "width": region[2] - region[0],
        "height": region[3] - region[1],
    }
    img = np.array(sct.grab(monitor))[:, :, :3]
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def clean_text(text):
    text = re.sub(r"[^A-Z0-9]", "", text.upper())
    return text.strip()

def main():
    print("🔍 Running Card 1 OCR Test (every 1s)... Press CTRL+C to stop.")
    try:
        while True:
            gray = grab_gray(card_1_region)
            _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
            raw_text = pytesseract.image_to_string(thresh, config='--psm 6')
            cleaned = clean_text(raw_text)

            print(f"\n🂠 Raw OCR: {repr(raw_text)}")
            print(f"✅ Cleaned: {cleaned}")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Test ended.")

if __name__ == "__main__":
    main()


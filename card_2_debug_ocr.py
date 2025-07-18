import pytesseract
import cv2
import numpy as np
from PIL import ImageGrab
import time
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === CARD ZONES ===
card_1_region = (1825, 940, 1872, 985)
card_2_region = (1867, 946, 1907, 976)
card_3_region = (1908, 946, 1933, 976)

def grab_gray(region):
    img = np.array(ImageGrab.grab(bbox=region))
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def clean_text(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper()).strip()

def extract_card(text):
    text = text.replace("10", "T")
    text = text.replace("20", "2")
    if text in ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]:
        return "10" if text == "T" else text
    return ""

def get_card_value(card):
    if card in ['2', '3', '4', '5', '6']:
        return +1
    elif card in ['7', '8', '9']:
        return 0
    elif card in ['10', 'J', 'Q', 'K', 'A']:
        return -1
    return 0

def main():
    print("🔍 Card OCR with Round Summary... Press CTRL+C to stop.")

    last_hand = []
    last_cleaned = []  # last OCR'd hand
    hand_confirm_count = 0
    hand_was_cleared = False
    hand_cleared_timer = None
    CLEAR_DELAY = 5.0  # seconds before confirmed clear
    a_visible_since = None
    last_a_hand = None

    try:
        while True:
            now = time.time()
            gray1 = grab_gray(card_1_region)
            gray2 = grab_gray(card_2_region)
            gray3 = grab_gray(card_3_region)

            _, thresh1 = cv2.threshold(gray1, 160, 255, cv2.THRESH_BINARY)
            _, thresh2 = cv2.threshold(gray2, 160, 255, cv2.THRESH_BINARY)
            _, thresh3 = cv2.threshold(gray3, 160, 255, cv2.THRESH_BINARY)

            raw1 = pytesseract.image_to_string(thresh1, config='--psm 6')
            raw2 = pytesseract.image_to_string(thresh2, config='--psm 6')
            raw3 = pytesseract.image_to_string(thresh3, config='--psm 6')

            c1 = extract_card(clean_text(raw1))
            c2 = extract_card(clean_text(raw2))
            c3 = extract_card(clean_text(raw3))

            hand = [c for c in [c1, c2, c3] if c]

            # === Discard incomplete reads
            if len(hand) == 1:
                # Optional debug output for skipped hands
                # print(f"Skipping 1-card hand: {hand}")
                continue  # skip phantom or incomplete hand

            # === Handle delayed hand clear
            if not hand:
                hand_confirm_count = 0
                last_cleaned = []
                if last_hand and hand_cleared_timer is None:
                    hand_cleared_timer = time.time()
                elif hand_cleared_timer and time.time() - hand_cleared_timer >= CLEAR_DELAY:
                    # Print summary from last_hand
                    delta = sum(get_card_value(c) for c in last_hand)
                    print(f"🧾 Last Hand: {last_hand} → Count: {delta:+}")
                    print("🧼 Hand cleared after 5s blank.")
                    last_hand = []
                    last_cleaned = []
                    hand_confirm_count = 0
                    hand_was_cleared = True
                    hand_cleared_timer = None
                a_visible_since = None
                last_a_hand = None
                continue
            else:
                hand_cleared_timer = None

            # === Track visibility for hands containing 'A'
            if 'A' in hand:
                if last_a_hand == hand:
                    if a_visible_since is None:
                        a_visible_since = now
                else:
                    last_a_hand = hand.copy()
                    a_visible_since = now
            else:
                last_a_hand = None
                a_visible_since = None

            # === Stability check before printing
            if hand == last_cleaned:
                hand_confirm_count += 1
            else:
                hand_confirm_count = 1
                last_cleaned = hand.copy()

            if hand_confirm_count < 2:
                continue

            # Avoid duplicate prints
            if hand == last_hand:
                continue

            # === Valid hand update with optional delay for 'A'
            should_print = True
            if 'A' in hand:
                if last_a_hand == hand and a_visible_since and now - a_visible_since >= 1:
                    should_print = True
                else:
                    should_print = False
            if should_print:
                print(f"🂠 Card 1: {c1}, Card 2: {c2}, Card 3: {c3} → ✅ Hand: {hand}")
                last_hand = hand.copy()
                hand_was_cleared = False

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n🛑 Test ended.")

if __name__ == "__main__":
    main()

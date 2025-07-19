import pytesseract
import cv2
import numpy as np
import mss
import hashlib
import time
import re

sct = mss.mss()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === UPDATED SCREEN REGIONS ===
your_hand_region = (1825, 943, 2033, 995)
dealer_hand_region = (380, 945, 525, 995)
active_hand_region = (370, 710, 578, 755)

# === HI-LO LOGIC ===
def get_card_value(card):
    if card in ['2', '3', '4', '5', '6']:
        return +1
    elif card in ['7', '8', '9']:
        return 0
    elif card in ['10', 'J', 'Q', 'K', 'A']:
        return -1
    return 0

def get_true_count(running, decks_left):
    return round(running / decks_left, 2) if decks_left > 0 else 0

def suggest_bet(tc):
    if tc <= 1:
        return "🟢"
    elif tc <= 2:
        return "🟡"
    elif tc <= 3:
        return "🟠"
    else:
        return "🔴"

# === OCR UTILS ===
def region_hash(image):
    return hashlib.md5(image.tobytes()).hexdigest()

def grab_region(region):
    monitor = {
        "top": region[1],
        "left": region[0],
        "width": region[2] - region[0],
        "height": region[3] - region[1],
    }
    img = np.array(sct.grab(monitor))[:, :, :3]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray

def clean_text(text):
    cleaned = re.sub(r"[^A-Z0-9\s]", "", text.upper())
    return re.sub(r"\s+", " ", cleaned).strip()

def extract_cards(text):
    text = text.replace("10", "T")
    parts = text.split()
    cards = []
    for part in parts:
        for ch in part:
            if ch in "23456789TJQKA":
                cards.append("10" if ch == "T" else ch)
    return cards

# === MAIN LOOP ===
def main():
    print("🎴 Auto Blackjack Counter v1.11 Running... Press CTRL+C to stop.")
    total_decks = 6
    running_count = 0
    cards_seen = 0
    buffer_time = 0.3

    regions = {
        "Your Hand": your_hand_region,
        "Dealer Hand": dealer_hand_region,
        "Active Hand": active_hand_region
    }

    last_hashes = {k: "" for k in regions}
    stable_since = {k: time.time() for k in regions}
    last_cards = {k: [] for k in regions}
    last_count = running_count
    last_ocr = {k: [] for k in regions}
    confirm_count = {k: 0 for k in regions}

    try:
        while True:
            now = time.time()

            for label, region in regions.items():
                gray = grab_region(region)
                h = region_hash(gray)

                if h != last_hashes[label]:
                    last_hashes[label] = h
                    stable_since[label] = now
                    continue

                if (now - stable_since[label]) < buffer_time:
                    continue

                text = pytesseract.image_to_string(gray, config='--psm 6')
                cleaned = clean_text(text)
                cards = extract_cards(cleaned)
                if len(cards) < 2:
                    continue

                # === Require 2x match to confirm
                if cards == last_ocr[label]:
                    confirm_count[label] += 1
                else:
                    confirm_count[label] = 1
                    last_ocr[label] = cards

                if confirm_count[label] < 2:
                    continue

                prev_cards = last_cards[label]

                if cards == prev_cards:
                    continue

                last_cards[label] = cards.copy()

                # === Count Delta
                count_delta = 0
                if len(cards) < len(prev_cards) or cards[:len(prev_cards)] != prev_cards:
                    count_delta = sum(get_card_value(c) for c in cards)
                    cards_seen += len(cards)
                    print(f"🔄 {label}: {cards} ➕ {count_delta:+}")
                elif len(cards) > len(prev_cards) and cards[:len(prev_cards)] == prev_cards:
                    new_cards = cards[len(prev_cards):]
                    count_delta = sum(get_card_value(c) for c in new_cards)
                    cards_seen += len(new_cards)
                    print(f"➕ {label}: {new_cards} ➕ {count_delta:+}")
                else:
                    continue

                running_count += count_delta
                decks_remaining = max(0.5, total_decks - (cards_seen / 52))
                true_count = get_true_count(running_count, decks_remaining)

                if running_count != last_count:
                    print(f"📊 Count: {running_count} | TC: {true_count} | Bet: {suggest_bet(true_count)}")
                    last_count = running_count

            time.sleep(0.25)

    except KeyboardInterrupt:
        print("\n🛑 Session ended.")
        print(f"Final Count: {running_count}, Cards Seen: {cards_seen}")

if __name__ == "__main__":
    main()

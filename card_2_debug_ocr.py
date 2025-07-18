import pytesseract
import cv2
import numpy as np
import mss
import time
import re
import os
from collections import deque

sct = mss.mss()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === CARD ZONES ===
card_1_region = (1825, 940, 1872, 985)
card_2_region = (1867, 946, 1907, 976)
card_3_region = (1908, 946, 1933, 976)
card_4_region = (1950, 946, 1973, 976)
card_5_region = (1826, 964, 1853, 996)
double_card_region = (1948, 985, 1983, 1013)
bj_counter_region = (1975, 875, 2016, 905)

# Persist last good blackjack counter total
last_bj_total = None

# === TEMPLATE LOADING ===
template_dir = os.path.join(os.path.dirname(__file__), "templates")
card_templates = {
    "A": cv2.imread(os.path.join(template_dir, "A.png"), 0),
    "10": cv2.imread(os.path.join(template_dir, "10.png"), 0),
    "J": cv2.imread(os.path.join(template_dir, "J.png"), 0),
    "Q": cv2.imread(os.path.join(template_dir, "Q.png"), 0),
    "K": cv2.imread(os.path.join(template_dir, "K.png"), 0),
}
digit_templates = {
    str(i): cv2.imread(os.path.join(template_dir, "digits", f"{i}.png"), 0)
    for i in range(10)
}


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
    return re.sub(r"[^A-Z0-9]", "", text.upper()).strip()

def clean_digits(text):
    return re.sub(r"\D", "", text)

def match_template(gray_img, templates, threshold=0.8):
    """Return the label of the first template that exceeds the threshold."""
    for label, tmpl in templates.items():
        if tmpl is None:
            continue
        res = cv2.matchTemplate(gray_img, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= threshold:
            return label
    return None

def has_changed(prev_img, curr_img, threshold=25, min_change_pixels=50):
    """Return True if the difference between images exceeds the threshold."""
    diff = cv2.absdiff(prev_img, curr_img)
    _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
    changed_pixels = cv2.countNonZero(thresh)
    return changed_pixels > min_change_pixels

def extract_card(text):
    text = text.strip().upper()

    # Normalize common OCR misreads
    if text in ["0", "O", "T"]:
        return "10"
    if text in ["1", "I", "L"]:
        return "1"
    if text == "Z":
        return "2"
    if text == "S":
        return "5"

    # Preserve 'A' — do not downgrade to '4' here
    if text == "A":
        return "A"

    if text in ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]:
        return text

    return ""

def get_card_value(card):
    if card in ['2', '3', '4', '5', '6']:
        return +1
    elif card in ['7', '8', '9']:
        return 0
    elif card in ['10', 'J', 'Q', 'K', 'A']:
        return -1
    return 0

def get_hand_total(cards):
    """Return blackjack total with soft-to-hard Ace adjustment."""
    total = 0
    aces = 0

    for c in cards:
        if c == 'A':
            total += 11
            aces += 1
        elif c in ['K', 'Q', 'J', '10']:
            total += 10
        else:
            try:
                total += int(c)
            except ValueError:
                pass

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total

def main():
    print("🔍 Card OCR with Round Summary... Press CTRL+C to stop.")
    global last_bj_total
    last_hand = []
    last_cleaned = []  # last OCR'd hand
    last_seen_valid_hand = []
    hand_confirm_count = 0
    running_count = 0
    hand_was_cleared = False
    hand_cleared_timer = None
    CLEAR_DELAY = 5.0  # seconds before confirmed clear
    a_visible_since = None
    last_a_hand = None

    # === Burst OCR Mode Settings ===
    burst_mode_active = False
    burst_mode_start = None
    BURST_DURATION = 4.0  # More time to capture final hits
    prev_card_regions = {
        "card_1": None,
        "card_2": None,
        "card_3": None,
        "card_4": None,
        "card_5": None,
        "bj_counter": None,
    }

    roi_buffers = {
        "card_1": deque(maxlen=10),
        "card_2": deque(maxlen=10),
        "card_3": deque(maxlen=10),
        "card_4": deque(maxlen=10),
        "card_5": deque(maxlen=10),
        "bj_counter": deque(maxlen=10),
    }

    try:
        while True:
            now = time.time()

            if burst_mode_active and (time.time() - burst_mode_start > BURST_DURATION):
                burst_mode_active = False
                print("🧯 Exiting burst OCR mode")
            gray1 = grab_gray(card_1_region)
            roi_buffers["card_1"].append(gray1)
            gray2 = grab_gray(card_2_region)
            roi_buffers["card_2"].append(gray2)
            gray3 = grab_gray(card_3_region)
            roi_buffers["card_3"].append(gray3)
            gray4 = grab_gray(card_4_region)
            roi_buffers["card_4"].append(gray4)
            gray5 = grab_gray(card_5_region)
            roi_buffers["card_5"].append(gray5)
            bj_gray = grab_gray(bj_counter_region)
            roi_buffers["bj_counter"].append(bj_gray)

            if prev_card_regions["card_1"] is None or has_changed(prev_card_regions["card_1"], gray1):
                print("🔄 Change detected in card_1 → triggering OCR")
                _, thresh1 = cv2.threshold(gray1, 160, 255, cv2.THRESH_BINARY)
                raw1 = pytesseract.image_to_string(thresh1, config='--psm 6')
                c1 = extract_card(clean_text(raw1))
                if not c1:
                    match = match_template(gray1, card_templates)
                    if match:
                        c1 = match
                        print(f"🔁 Template matched card_1: {c1}")
                prev_card_regions["card_1"] = gray1
            else:
                c1 = ""

            if prev_card_regions["card_2"] is None or has_changed(prev_card_regions["card_2"], gray2):
                print("🔄 Change detected in card_2 → triggering OCR")
                _, thresh2 = cv2.threshold(gray2, 160, 255, cv2.THRESH_BINARY)
                raw2 = pytesseract.image_to_string(thresh2, config='--psm 6')
                c2 = extract_card(clean_text(raw2))
                if not c2:
                    match = match_template(gray2, card_templates)
                    if match:
                        c2 = match
                        print(f"🔁 Template matched card_2: {c2}")
                prev_card_regions["card_2"] = gray2
            else:
                c2 = ""

            if prev_card_regions["card_3"] is None or has_changed(prev_card_regions["card_3"], gray3):
                print("🔄 Change detected in card_3 → triggering OCR")
                _, thresh3 = cv2.threshold(gray3, 160, 255, cv2.THRESH_BINARY)
                raw3 = pytesseract.image_to_string(thresh3, config='--psm 6')
                regular_c3 = extract_card(clean_text(raw3))
                if not regular_c3:
                    match = match_template(gray3, card_templates)
                    if match:
                        regular_c3 = match
                        print(f"🔁 Template matched card_3: {regular_c3}")
                prev_card_regions["card_3"] = gray3
            else:
                regular_c3 = ""

            if prev_card_regions["card_4"] is None or has_changed(prev_card_regions["card_4"], gray4):
                print("🔄 Change detected in card_4 → triggering OCR")
                _, thresh4 = cv2.threshold(gray4, 160, 255, cv2.THRESH_BINARY)
                raw4 = pytesseract.image_to_string(thresh4, config='--psm 6')
                c4 = extract_card(clean_text(raw4))
                if not c4:
                    match = match_template(gray4, card_templates)
                    if match:
                        c4 = match
                        print(f"🔁 Template matched card_4: {c4}")
                prev_card_regions["card_4"] = gray4
            else:
                c4 = ""

            if prev_card_regions["card_5"] is None or has_changed(prev_card_regions["card_5"], gray5):
                print("🔄 Change detected in card_5 → triggering OCR")
                _, thresh5 = cv2.threshold(gray5, 160, 255, cv2.THRESH_BINARY)
                raw5 = pytesseract.image_to_string(thresh5, config='--psm 6')
                c5 = extract_card(clean_text(raw5))
                if not c5:
                    match = match_template(gray5, card_templates)
                    if match:
                        c5 = match
                        print(f"🔁 Template matched card_5: {c5}")
                prev_card_regions["card_5"] = gray5
            else:
                c5 = ""

            if prev_card_regions["bj_counter"] is None or has_changed(prev_card_regions["bj_counter"], bj_gray):
                print("🔄 Change detected in bj_counter → triggering OCR")
                _, bj_thresh = cv2.threshold(bj_gray, 160, 255, cv2.THRESH_BINARY)
                bj_raw = pytesseract.image_to_string(bj_thresh, config='--psm 6')
                bj_counter = clean_digits(bj_raw)
                if not bj_counter or len(bj_counter) < 2:
                    matched = match_template(bj_gray, digit_templates)
                    if matched:
                        bj_counter = matched
                        print(f"🔁 Template matched bj_total: {bj_counter}")
                prev_card_regions["bj_counter"] = bj_gray
            else:
                bj_counter = ""

            # === Double-Down Card Support ===
            double_gray = grab_gray(double_card_region)
            rotated = cv2.rotate(double_gray, cv2.ROTATE_90_CLOCKWISE)
            raw_double = pytesseract.image_to_string(rotated, config='--psm 6')
            double_card = extract_card(clean_text(raw_double))

            third_card = double_card if double_card else regular_c3

            cards = [c1, c2, third_card, c4, c5]
            hand = [c for c in cards if c]

            if len(hand) >= 3 and get_hand_total(hand) < 18:
                print(f"⚠️ Low-value hand with 3+ cards: {hand} → possible OCR miss")

            if len(hand) == 3 and not burst_mode_active:
                burst_mode_active = True
                burst_mode_start = time.time()
                print("🚀 Entering burst OCR mode after 3rd card")

            if len(hand) >= 2:
                last_seen_valid_hand = hand.copy()

            # === Fallback Blackjack detection using on-screen counter
            if bj_counter == "21" and len(hand) == 1:
                hand = ['A', '10']
                print("♠ Blackjack inferred from counter → Hand: ['A', '10']")
                last_hand = hand.copy()
                last_cleaned = hand.copy()
                hand_confirm_count = 2  # force confirmation bypass

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
                    hand_to_count = last_hand if last_hand else last_seen_valid_hand
                    if hand_to_count:
                        delta = sum(get_card_value(c) for c in hand_to_count)
                        print(f"🧾 Last Hand: {hand_to_count} → Count: {delta:+}")

                        running_count += delta

                        bj_img = grab_gray(bj_counter_region)
                        bj_raw = pytesseract.image_to_string(bj_img, config='--psm 6')
                        bj_counter = re.sub(r"[^0-9]", "", bj_raw).strip()

                        try:
                            parsed = int(bj_counter)
                            if 12 <= parsed <= 26:
                                bj_total = parsed
                                last_bj_total = bj_total  # persist good value
                            else:
                                print(f"🚫 Discarding invalid bj_total: {parsed}")
                                bj_total = None
                        except ValueError:
                            bj_total = None


                        hand_total = get_hand_total(hand_to_count)

                        # 🔁 Retry OCR from snapshot buffer if hand seems under-read
                        if bj_total is None and len(hand_to_count) in [3, 4] and hand_total < 18:
                            print(f"📦 Attempting to recover missed cards from buffer...")

                            for card_key in ["card_3", "card_4", "card_5"]:
                                if card_key not in roi_buffers:
                                    continue
                                for img in reversed(roi_buffers[card_key]):
                                    raw = pytesseract.image_to_string(img, config='--psm 6')
                                    cleaned = clean_text(raw)
                                    extracted = extract_card(cleaned)
                                    if not extracted:
                                        match = match_template(img, card_templates)
                                        if match:
                                            extracted = match
                                            print(f"🔁 Template matched {card_key} from buffer: {extracted}")
                                    if extracted and extracted not in hand_to_count:
                                        hand_to_count.append(extracted)
                                        print(f"🧩 Added recovered card from buffer: {extracted}")
                                        break  # only take one candidate per slot

                        # ✅ Bust inference when bj_total is unreadable
                        if bj_total is None and hand_total >= 22:
                            print("🔁 bj_total is None — scanning snapshot buffer for possible counter")
                            for buffered_img in reversed(roi_buffers["bj_counter"]):
                                raw = pytesseract.image_to_string(buffered_img, config='--psm 6')
                                cleaned = re.sub(r"[^0-9]", "", raw)
                                try:
                                    parsed = int(cleaned)
                                    if 22 <= parsed <= 26:
                                        bj_total = parsed
                                        print(f"📦 Snapshot OCR recovered bj_total = {bj_total}")
                                        break
                                except ValueError:
                                    continue

                            if bj_total is None:
                                print(f"🛡️ Inferring bust due to hand_total = {hand_total} (bj_total OCR failed)")
                                bj_total = hand_total  # force phantom correction path

                        if bj_total is None and last_bj_total and 22 <= last_bj_total <= 26:
                            bj_total = last_bj_total
                            print(f"♻️ Reusing last bj_total = {bj_total} due to OCR failure")

                        if bj_total is not None and 22 <= bj_total <= 26 and bj_total - hand_total >= 2:
                            # Remove the previously added raw hand delta before applying phantom card logic
                            running_count -= delta
                            phantom_card_value = bj_total - hand_total
                            if 'A' in hand_to_count and phantom_card_value == 3:
                                print("🧐 POSSIBLE OCR SLIP: 'A' might actually be a 4 — review image manually")

                            # Map the difference to a likely card rank
                            if phantom_card_value == 10:
                                phantom_card = '10'
                            elif phantom_card_value == 11:
                                phantom_card = 'A'
                            elif 2 <= phantom_card_value <= 6:
                                phantom_card = str(phantom_card_value)
                            else:
                                phantom_card = '10'

                            phantom_hi_lo_value = get_card_value(phantom_card)

                            running_count += phantom_hi_lo_value
                            print(
                                f"⚠️ Bust mismatch detected: Hand value = {hand_total}, Counter = {bj_total} → Phantom {phantom_card} added (Hi-Lo: {phantom_hi_lo_value:+})"
                            )

                        last_bj_total = None
                        print(
                            f"🧪 bj_total: {bj_total}, hand_total: {hand_total}, delta: {bj_total - hand_total if bj_total else 'N/A'}"
                        )

                    print("🧼 Hand cleared after 5s blank.")
                    last_hand = []
                    last_cleaned = []
                    last_seen_valid_hand = []
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
                print(f"🂠 Card 1: {c1}, Card 2: {c2}, Card 3: {third_card}, Card 4: {c4}, Card 5: {c5} → ✅ Hand: {hand}")
                last_hand = hand.copy()
                hand_was_cleared = False

            time.sleep(0.05 if burst_mode_active else 0.5)

    except KeyboardInterrupt:
        print("\n🛑 Test ended.")

if __name__ == "__main__":
    main()

# blackjack_counter_v1.2.py

def get_card_value(card):
    card = card.upper()
    if card in ['2', '3', '4', '5', '6']:
        return +1
    elif card in ['7', '8', '9']:
        return 0
    elif card in ['10', 'J', 'Q', 'K', 'A']:
        return -1
    else:
        return 0

def get_true_count(running_count, decks_remaining):
    return round(running_count / decks_remaining, 2) if decks_remaining > 0 else 0

def suggest_bet(true_count):
    if true_count <= 1:
        return "🟢 Minimum bet"
    elif true_count <= 2:
        return "🟡 2 units"
    elif true_count <= 3:
        return "🟠 4 units"
    else:
        return "🔴 Max bet"

def display_count(running_count, cards_seen, total_decks):
    decks_remaining = max(0.5, total_decks - (cards_seen / 52))
    true_count = get_true_count(running_count, decks_remaining)
    print(f"\n📊 Running Count: {running_count}")
    print(f"📘 Decks Remaining: {decks_remaining:.2f}")
    print(f"🎯 True Count: {true_count}")
    print(f"💰 Suggested Bet: {suggest_bet(true_count)}")
    return decks_remaining, true_count

def main():
    print("🎴 Blackjack Counter — Hi-Lo System (v1.2)")

    total_decks = float(input("🔢 Total decks in shoe (e.g., 6 or 8): "))
    running_count = 0
    cards_seen = 0

    while True:
        print("\n🆕 Starting New Hand")
        print("⏹ Type: EXIT = quit | RESET = new shoe | NEXT = next hand")

        # INITIAL DEAL
        initial = input("🔹 Enter INITIAL deal cards (e.g. '10 4 A K'):\n> ").strip().upper().split()
        if initial == ['EXIT']:
            print("🛑 Exiting. Final Count:", running_count)
            break
        if initial == ['RESET']:
            running_count = 0
            cards_seen = 0
            print("♻️ Shoe reset — running count and cards seen cleared.")
            continue

        for card in initial:
            running_count += get_card_value(card)
            cards_seen += 1

        decks_remaining, true_count = display_count(running_count, cards_seen, total_decks)

        # ADDITIONAL CARDS
        while True:
            more = input("➕ Enter additional cards (HITs/dealer hole), or type NEXT/RESET/EXIT:\n> ").strip().upper().split()
            if more == ['NEXT']:
                break
            if more == ['EXIT']:
                print("🛑 Exiting. Final Count:", running_count)
                return
            if more == ['RESET']:
                running_count = 0
                cards_seen = 0
                print("♻️ Shoe reset — running count and cards seen cleared.")
                break

            for card in more:
                running_count += get_card_value(card)
                cards_seen += 1

            decks_remaining, true_count = display_count(running_count, cards_seen, total_decks)

if __name__ == "__main__":
    main()

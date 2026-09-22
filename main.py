import csv
import json
import os
import random
import sys

CSV_FILE = "elements.csv"
USER_DATA_FILE = "userdata.txt"


def get_key():
    """Reads a single keypress without requiring the Enter key (Cross-Platform)."""
    try:
        # Windows
        import msvcrt

        ch = msvcrt.getch()
        if ch == b"\x03":  # Handle Ctrl+C
            raise KeyboardInterrupt
        return ch.decode("utf-8", errors="ignore")
    except ImportError:
        # Unix / Linux / macOS
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x03":  # Handle Ctrl+C
                raise KeyboardInterrupt
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def load_csv(filename):
    """Parses local CSV file, filtering internally by atomic number ranges."""
    filtered = []
    with open(filename, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            raw_num = (
                row.get("AtomicNumber")
                or row.get("Atomic Number")
                or row.get("Number")
            )
            if raw_num is not None:
                try:
                    num = int(raw_num)
                    # Keep ranges 1-38, 46-56, and 78-98
                    if (1 <= num <= 38) or (46 <= num <= 56) or (78 <= num <= 98):
                        filtered.append(row)
                except ValueError:
                    continue
    return filtered


def load_user_data():
    """Loads persistent user data from userdata.txt."""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "round_number": 1,
        "round_history": [],  # List of dicts: {"pct": float, "deck_size": int}
        "element_stats": {},  # Symbol -> {"correct": int, "incorrect": int}
    }


def save_user_data(data):
    """Saves user data back to userdata.txt in JSON format."""
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save user data: {e}")


def get_weak_elements(all_elements, user_data):
    """Returns elements where historical wrong rate > 25%."""
    weak = []
    stats = user_data.get("element_stats", {})
    for row in all_elements:
        symbol = row.get("Symbol", "")
        elem_stat = stats.get(symbol, {"correct": 0, "incorrect": 0})
        total = elem_stat["correct"] + elem_stat["incorrect"]
        if total > 0 and (elem_stat["incorrect"] / total) > 0.25:
            weak.append(row)
    return weak


def display_chart(user_data, total_count):
    """Displays ASCII art chart ONLY for rounds where all 70 (total_count) elements were tried."""
    raw_history = user_data.get("round_history", [])

    full_rounds = []
    for entry in raw_history:
        if isinstance(entry, dict):
            if entry.get("deck_size") == total_count:
                full_rounds.append(entry["pct"])
        elif isinstance(entry, (int, float)):
            full_rounds.append(entry)

    print("\n" + "=" * 40)
    print("     FULL 70-ELEMENT PERFORMANCE CHART")
    print("=" * 40)

    if not full_rounds:
        print(f"No rounds with all {total_count} elements completed yet.\n")
        return

    print("Full-Round Scores:")
    for idx, pct in enumerate(full_rounds, 1):
        print(f"  Attempt #{idx}: {pct:.1f}%")

    print("\n--- Progress Chart (1 '#' per 10%) ---")
    width = len(full_rounds)

    for level in range(10, 0, -1):
        label = f"{level * 10:3d}% |"
        row_str = ""
        for score in full_rounds:
            blocks = int(score // 10)
            if blocks >= level:
                row_str += "#"
            else:
                row_str += " "
        print(f"{label}{row_str}")

    print("     +" + "-" * width)
    axis_labels = "".join(str(i % 10) for i in range(1, width + 1))
    print(f" Round{axis_labels}\n")


def print_stats(correct, incorrect):
    """Prints current session counts and percentages."""
    total = correct + incorrect
    print("\n" + "=" * 32)
    print("          SCORE SUMMARY")
    print("=" * 32)

    if total == 0:
        print("No elements were answered.")
    else:
        pct_correct = (correct / total) * 100
        pct_incorrect = (incorrect / total) * 100
        print(f"Correct (1):   {correct} ({pct_correct:.1f}%)")
        print(f"Incorrect (2): {incorrect} ({pct_incorrect:.1f}%)")
        print(f"Total:         {total}")

    print("=" * 32 + "\n")


def record_round_completion(user_data, correct, incorrect, deck_size):
    """Updates user data history and round count at end of a session or interrupt."""
    total = correct + incorrect
    if total > 0:
        pct = (correct / total) * 100
        user_data["round_history"].append({
            "pct": pct,
            "deck_size": deck_size
        })

    user_data["round_number"] += 1
    save_user_data(user_data)


def main():
    print(f"Loading '{CSV_FILE}' from local directory...")
    try:
        all_elements = load_csv(CSV_FILE)
        total_count = len(all_elements)
        print(f"Loaded {total_count} elements.\n")
    except FileNotFoundError:
        print(f"Error: Could not find '{CSV_FILE}' in the current folder.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    user_data = load_user_data()

    # Startup Menu
    while True:
        print(f"=== Main Menu (Current Round #{user_data['round_number']}) ===")
        print(f"  [1] All {total_count} elements")
        weak_count = len(get_weak_elements(all_elements, user_data))
        print(f"  [2] Elements wrong > 25% historically ({weak_count} elements)")
        print("  [3] Show score history & ASCII chart (Full 70-element rounds)")
        print("Choice: ", end="", flush=True)

        choice = get_key()
        print(choice)

        if choice == "1":
            current_deck = list(all_elements)
            break
        elif choice == "2":
            weak = get_weak_elements(all_elements, user_data)
            if not weak:
                print("\nNo elements have a >25% error rate yet! Starting with all elements.\n")
                current_deck = list(all_elements)
            else:
                current_deck = weak
            break
        elif choice == "3":
            display_chart(user_data, total_count)
        else:
            print("Invalid option. Please press 1, 2, or 3.\n")

    print("\n--- Flashcards Ready ---")
    print("• Press ANY key to reveal the name")
    print("• Press 1 for Correct, 2 for Incorrect")
    print("• Press 3 to swap the answer for the PREVIOUS question")
    print("• Press Ctrl+C at any time to exit and save stats\n")

    correct = 0
    incorrect = 0

    try:
        while True:
            correct = 0
            incorrect = 0
            missed_this_round = []
            deck_size = len(current_deck)

            # Tracking variables for previous question swap
            prev_row = None
            prev_result = None  # '1' or '2'

            random.shuffle(current_deck)
            print(f"--- Round #{user_data['round_number']} ({deck_size} elements) ---")

            for row in current_deck:
                symbol = row.get("Symbol", "N/A")
                name = row.get("Element") or row.get("Name") or "N/A"

                if symbol not in user_data["element_stats"]:
                    user_data["element_stats"][symbol] = {"correct": 0, "incorrect": 0}

                # 1. Output Symbol and wait for keypress
                print(f"Symbol: {symbol}", end="", flush=True)
                get_key()

                # 2. Output Name
                print(f"\nName:   {name}")

                # 3. Handle key input
                while True:
                    key = get_key()
                    if key == "1":
                        correct += 1
                        user_data["element_stats"][symbol]["correct"] += 1
                        print("Result: Correct (1)")
                        prev_row = row
                        prev_result = "1"
                        break
                    elif key == "2":
                        incorrect += 1
                        user_data["element_stats"][symbol]["incorrect"] += 1
                        missed_this_round.append(row)
                        print("Result: Incorrect (2)")
                        prev_row = row
                        prev_result = "2"
                        break
                    elif key == "3":
                        if prev_row is None:
                            print("\n[No previous question in this round to swap!]")
                            print(f"Symbol: {symbol}")
                            print(f"Name:   {name}")
                        else:
                            prev_sym = prev_row.get("Symbol", "N/A")
                            if prev_result == "1":
                                # Swap Correct -> Incorrect
                                correct -= 1
                                incorrect += 1
                                user_data["element_stats"][prev_sym]["correct"] -= 1
                                user_data["element_stats"][prev_sym]["incorrect"] += 1
                                missed_this_round.append(prev_row)
                                prev_result = "2"
                                print(f"\n[Swapped previous answer ({prev_sym}) from Correct -> Incorrect!]")
                            elif prev_result == "2":
                                # Swap Incorrect -> Correct
                                incorrect -= 1
                                correct += 1
                                user_data["element_stats"][prev_sym]["incorrect"] -= 1
                                user_data["element_stats"][prev_sym]["correct"] += 1
                                if prev_row in missed_this_round:
                                    missed_this_round.remove(prev_row)
                                prev_result = "1"
                                print(f"\n[Swapped previous answer ({prev_sym}) from Incorrect -> Correct!]")

                            # Re-ask the current question
                            print(f"\nRe-asking current element:")
                            print(f"Symbol: {symbol}")
                            print(f"Name:   {name}")

                print()

            # End of round processing
            print(f"Completed all {deck_size} elements in this round!")
            print_stats(correct, incorrect)
            record_round_completion(user_data, correct, incorrect, deck_size)

            # Next Round Selection Menu
            print("Select the set for Round #" + str(user_data["round_number"]) + ":")
            print(f"  [1] All {total_count} elements")
            print(f"  [2] Only elements missed in this round ({len(missed_this_round)})")
            weak = get_weak_elements(all_elements, user_data)
            print(f"  [3] Elements wrong > 25% historically ({len(weak)})")
            print("Choice: ", end="", flush=True)

            while True:
                choice = get_key()
                if choice == "1":
                    print("1 (All elements)\n")
                    current_deck = list(all_elements)
                    break
                elif choice == "2":
                    print(f"2 ({len(missed_this_round)} missed elements)\n")
                    current_deck = list(missed_this_round) if missed_this_round else list(all_elements)
                    break
                elif choice == "3":
                    print(f"3 ({len(weak)} historically weak elements)\n")
                    current_deck = weak if weak else list(all_elements)
                    break

    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
        print_stats(correct, incorrect)
        record_round_completion(user_data, correct, incorrect, len(current_deck))
        print(f"Saved progress to '{USER_DATA_FILE}'. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

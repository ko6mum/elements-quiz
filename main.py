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
                    # Keep ranges 1-38, 46-56, and 78-98 (70 elements)
                    if (1 <= num <= 38) or (46 <= num <= 56) or (78 <= num <= 98):
                        filtered.append(row)
                except ValueError:
                    continue
    return filtered


def build_full_deck(all_elements):
    """Creates a 140-item deck: 2 questions per element (sym->name & name->sym)."""
    deck = []
    for row in all_elements:
        deck.append({"row": row, "direction": "sym_to_name"})
        deck.append({"row": row, "direction": "name_to_sym"})
    return deck


def migrate_user_data(data):
    """Converts old userdata structure to option #2:

    Assigns 100% of historical stats to 'sym_to_name' and starts 'name_to_sym'
    fresh at 0.
    """
    # 1. Migrate round_history if scores were stored as raw numbers
    new_history = []
    for entry in data.get("round_history", []):
        if isinstance(entry, (int, float)):
            new_history.append({"pct": float(entry), "deck_size": 70})
        elif isinstance(entry, dict):
            new_history.append(entry)
    data["round_history"] = new_history

    # 2. Migrate old element_stats: past data -> sym_to_name, 0 -> name_to_sym
    old_stats = data.get("element_stats", {})
    new_stats = {}
    for symbol, stat in old_stats.items():
        if isinstance(stat, dict):
            if "correct" in stat or "incorrect" in stat:
                c = stat.get("correct", 0)
                i = stat.get("incorrect", 0)
                new_stats[symbol] = {
                    "sym_to_name": {"correct": c, "incorrect": i},
                    "name_to_sym": {"correct": 0, "incorrect": 0},
                }
            else:
                new_stats[symbol] = stat
        else:
            new_stats[symbol] = stat

    data["element_stats"] = new_stats
    return data


def load_user_data():
    """Loads persistent user data from userdata.txt and migrates old formats."""
    data = {
        "round_number": 1,
        "round_history": [],
        "element_stats": {},
    }

    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception as e:
            print(
                f"Warning: Could not parse '{USER_DATA_FILE}', starting fresh."
                f" ({e})"
            )

    return migrate_user_data(data)


def save_user_data(data):
    """Saves user data back to userdata.txt in JSON format."""
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save user data: {e}")


def update_stat(user_data, symbol, direction, field, delta):
    """Safely updates stats for a specific symbol and question direction."""
    if symbol not in user_data["element_stats"]:
        user_data["element_stats"][symbol] = {}

    if direction not in user_data["element_stats"][symbol]:
        user_data["element_stats"][symbol][direction] = {
            "correct": 0,
            "incorrect": 0,
        }

    user_data["element_stats"][symbol][direction][field] += delta


def get_weak_questions(all_elements, user_data):
    """Returns question items where historical wrong rate > 25%."""
    weak = []
    stats = user_data.get("element_stats", {})
    for row in all_elements:
        symbol = row.get("Symbol", "")
        elem_stats = stats.get(symbol, {})

        if isinstance(elem_stats, dict):
            for direction in ["sym_to_name", "name_to_sym"]:
                dir_stat = elem_stats.get(
                    direction, {"correct": 0, "incorrect": 0}
                )
                if isinstance(dir_stat, dict):
                    correct = dir_stat.get("correct", 0)
                    incorrect = dir_stat.get("incorrect", 0)
                    total = correct + incorrect
                    if total > 0 and (incorrect / total) > 0.25:
                        weak.append({"row": row, "direction": direction})
    return weak


def display_chart(user_data, total_count):
    """Displays ASCII art chart for rounds matching full decks (140 or legacy 70)."""
    raw_history = user_data.get("round_history", [])

    full_rounds = []
    for entry in raw_history:
        if isinstance(entry, dict):
            if entry.get("deck_size") in [total_count, 70]:
                full_rounds.append(entry["pct"])

    print("\n" + "=" * 44)
    print("           PERFORMANCE CHART")
    print("=" * 44)

    if not full_rounds:
        print("No completed full rounds available to chart yet.\n")
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
        print("No questions were answered.")
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
        user_data["round_history"].append(
            {"pct": pct, "deck_size": deck_size}
        )

    user_data["round_number"] += 1
    save_user_data(user_data)


def main():
    print(f"Loading '{CSV_FILE}' from local directory...")
    try:
        all_elements = load_csv(CSV_FILE)
        full_deck = build_full_deck(all_elements)
        total_count = len(full_deck)  # 140 questions
        print(
            f"Loaded {len(all_elements)} elements ({total_count} total questions).\n"
        )
    except FileNotFoundError:
        print(f"Error: Could not find '{CSV_FILE}' in the current folder.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    user_data = load_user_data()
    save_user_data(user_data)

    # Startup Menu
    while True:
        print(f"=== Main Menu (Current Round #{user_data['round_number']}) ===")
        print(f"  [1] All {total_count} questions")
        weak_questions = get_weak_questions(all_elements, user_data)
        print(
            f"  [2] Questions wrong > 25% historically ({len(weak_questions)} questions)"
        )
        print("  [3] Show score history & ASCII chart")
        print("Choice: ", end="", flush=True)

        choice = get_key()
        print(choice)

        if choice == "1":
            current_deck = list(full_deck)
            break
        elif choice == "2":
            if not weak_questions:
                print(
                    "\nNo questions have a >25% error rate yet! Starting with all questions.\n"
                )
                current_deck = list(full_deck)
            else:
                current_deck = list(weak_questions)
            break
        elif choice == "3":
            display_chart(user_data, total_count)
        else:
            print("Invalid option. Please press 1, 2, or 3.\n")

    print("\n--- Flashcards Ready ---")
    print("• Press ANY key to reveal the answer")
    print("• Press 1 for Correct, 2 for Incorrect")
    print("• Press 3 to swap the answer for the PREVIOUS question")
    print("• Press Ctrl+C at any time to exit and save stats\n")

    try:
        while True:
            correct = 0
            incorrect = 0
            missed_this_round = []
            deck_size = len(current_deck)

            prev_item = None
            prev_result = None

            random.shuffle(current_deck)
            print(
                f"--- Round #{user_data['round_number']} ({deck_size} questions) ---"
            )

            for item in current_deck:
                row = item["row"]
                direction = item["direction"]
                symbol = row.get("Symbol", "N/A")
                name = row.get("Element") or row.get("Name") or "N/A"

                # 1. Output Prompt
                if direction == "sym_to_name":
                    print(f"Symbol: {symbol}", end="", flush=True)
                    get_key()
                    print(f"\nName:   {name}")
                else:
                    print(f"Name:   {name}", end="", flush=True)
                    get_key()
                    print(f"\nSymbol: {symbol}")

                # 2. Key input loop
                while True:
                    key = get_key()
                    if key == "1":
                        correct += 1
                        update_stat(user_data, symbol, direction, "correct", 1)
                        print("Result: Correct (1)")
                        prev_item = item
                        prev_result = "1"
                        break
                    elif key == "2":
                        incorrect += 1
                        update_stat(
                            user_data, symbol, direction, "incorrect", 1
                        )
                        missed_this_round.append(item)
                        print("Result: Incorrect (2)")
                        prev_item = item
                        prev_result = "2"
                        break
                    elif key == "3":
                        if prev_item is None:
                            print(
                                "\n[No previous question in this round to swap!]"
                            )
                            if direction == "sym_to_name":
                                print(f"Symbol: {symbol}\nName:   {name}")
                            else:
                                print(f"Name:   {name}\nSymbol: {symbol}")
                        else:
                            prev_sym = prev_item["row"].get("Symbol", "N/A")
                            prev_dir = prev_item["direction"]
                            dir_label = (
                                "Symbol->Name"
                                if prev_dir == "sym_to_name"
                                else "Name->Symbol"
                            )

                            if prev_result == "1":
                                correct -= 1
                                incorrect += 1
                                update_stat(
                                    user_data,
                                    prev_sym,
                                    prev_dir,
                                    "correct",
                                    -1,
                                )
                                update_stat(
                                    user_data,
                                    prev_sym,
                                    prev_dir,
                                    "incorrect",
                                    1,
                                )
                                missed_this_round.append(prev_item)
                                prev_result = "2"
                                print(
                                    f"\n[Swapped previous answer ({prev_sym} [{dir_label}]) from Correct -> Incorrect!]"
                                )
                            elif prev_result == "2":
                                incorrect -= 1
                                correct += 1
                                update_stat(
                                    user_data,
                                    prev_sym,
                                    prev_dir,
                                    "incorrect",
                                    -1,
                                )
                                update_stat(
                                    user_data,
                                    prev_sym,
                                    prev_dir,
                                    "correct",
                                    1,
                                )
                                if prev_item in missed_this_round:
                                    missed_this_round.remove(prev_item)
                                prev_result = "1"
                                print(
                                    f"\n[Swapped previous answer ({prev_sym} [{dir_label}]) from Incorrect -> Correct!]"
                                )

                            print("\nRe-asking current question:")
                            if direction == "sym_to_name":
                                print(f"Symbol: {symbol}\nName:   {name}")
                            else:
                                print(f"Name:   {name}\nSymbol: {symbol}")

                print()

            print(f"Completed all {deck_size} questions in this round!")
            print_stats(correct, incorrect)
            record_round_completion(user_data, correct, incorrect, deck_size)

            print(
                "Select the set for Round #"
                + str(user_data["round_number"])
                + ":"
            )
            print(f"  [1] All {total_count} questions")
            print(
                f"  [2] Only questions missed in this round ({len(missed_this_round)})"
            )
            weak = get_weak_questions(all_elements, user_data)
            print(f"  [3] Questions wrong > 25% historically ({len(weak)})")
            print("Choice: ", end="", flush=True)

            while True:
                choice = get_key()
                if choice == "1":
                    print("1 (All questions)\n")
                    current_deck = list(full_deck)
                    break
                elif choice == "2":
                    print(f"2 ({len(missed_this_round)} missed questions)\n")
                    current_deck = (
                        list(missed_this_round)
                        if missed_this_round
                        else list(full_deck)
                    )
                    break
                elif choice == "3":
                    print(f"3 ({len(weak)} historically weak questions)\n")
                    current_deck = list(weak) if weak else list(full_deck)
                    break

    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
        print_stats(correct, incorrect)
        record_round_completion(
            user_data, correct, incorrect, len(current_deck)
        )
        print(f"Saved progress to '{USER_DATA_FILE}'. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

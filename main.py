import csv
import random
import sys

# Local CSV file in the same directory
CSV_FILE = "elements.csv"


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


def print_stats(correct, incorrect):
    """Prints total counts and percentages for correct/incorrect responses."""
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


def main():
    print(f"Loading '{CSV_FILE}' from local directory...")
    try:
        elements = load_csv(CSV_FILE)
        total_count = len(elements)
        print(f"Loaded {total_count} elements.\n")
    except FileNotFoundError:
        print(f"Error: Could not find '{CSV_FILE}' in the current folder.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    print("--- Flashcards Ready ---")
    print("• Press ANY key to reveal the name")
    print("• Press 1 for Correct, 2 for Incorrect")
    print("• Press Ctrl+C at any time to exit and view stats\n")

    round_number = 1
    correct = 0
    incorrect = 0

    try:
        while True:
            # Reset score variables for each full pass
            correct = 0
            incorrect = 0

            # Reshuffle elements for a fixed random order this round
            random.shuffle(elements)

            print(f"--- Round {round_number} ---")

            for row in elements:
                symbol = row.get("Symbol", "N/A")
                name = row.get("Element") or row.get("Name") or "N/A"

                # 1. Output Symbol and wait for any single keypress
                print(f"Symbol: {symbol}", end="", flush=True)
                get_key()

                # 2. Output Name immediately
                print(f"\nName:   {name}")

                # 3. Wait for single keypress '1' or '2'
                while True:
                    key = get_key()
                    if key == "1":
                        correct += 1
                        print("Result: Correct (1)")
                        break
                    elif key == "2":
                        incorrect += 1
                        print("Result: Incorrect (2)")
                        break

                # Empty line between elements
                print()

            # End of round summary
            print(f"Completed all {total_count} elements!")
            print_stats(correct, incorrect)

            round_number += 1

    except KeyboardInterrupt:
        print("\n\nProgram stopped by user.")
        print_stats(correct, incorrect)
        sys.exit(0)


if __name__ == "__main__":
    main()

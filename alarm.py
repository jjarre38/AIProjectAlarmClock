import threading
import time
from datetime import datetime, timedelta


def ask_for_time():
    """Keep asking until the user enters a valid HH:MM time (24-hour)."""
    while True:
        text = input("Set alarm time (HH:MM, 24-hour, e.g. 18:30): ").strip()
        try:
            return datetime.strptime(text, "%H:%M").time()
        except ValueError:
            print("That doesn't look right. Use HH:MM, like 07:45 or 18:30.")


def next_occurrence(alarm_time):
    """Turn a time of day into the next datetime when it will occur."""
    now = datetime.now()
    target = now.replace(
        hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0
    )
    if target <= now:  # already passed today, so use tomorrow
        target += timedelta(days=1)
    return target


def wait_for_turn_off(stop_event):
    """Decides when the alarm is turned off.

    Blocks until the user does the required action, then sets stop_event.
    Right now the action is typing 'off' and pressing Enter. Replace the
    body with anything else (solve a math problem, wave at a camera, etc.)
    and the rest of the program doesn't need to change.
    """
    while True:
        answer = input().strip().lower()
        if answer == "off":
            stop_event.set()
            return
        print("Type 'off' and press Enter to stop the alarm.")


def trigger_alarm():
    stop_event = threading.Event()

    # Listen for the user's response in the background so the alarm
    # can keep going while we wait.
    listener = threading.Thread(
        target=wait_for_turn_off, args=(stop_event,), daemon=True
    )
    listener.start()

    print("\nType 'off' and press Enter to stop the alarm.\n")
    while not stop_event.is_set():
        print("Your alarm is going off")
        stop_event.wait(1)  # pause 1 second, but wake instantly if turned off

    print("Alarm turned off.")


def main():
    alarm_time = ask_for_time()
    target = next_occurrence(alarm_time)
    print(f"Alarm set for {target:%A %H:%M}. Press Ctrl+C to cancel.")

    try:
        while datetime.now() < target:
            time.sleep(1)  # check once per second
    except KeyboardInterrupt:
        print("\nAlarm cancelled.")
        return

    trigger_alarm()


if __name__ == "__main__":
    main()
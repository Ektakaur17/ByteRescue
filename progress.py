# progress.py

import time


def progress_monitor(total_size, processed_state, lock):
    """
    Display live scan progress in the console.
    """
    while True:
        with lock:
            current = processed_state["bytes"]

        percent = 0 if total_size == 0 else min((current / total_size) * 100, 100)

        bar_length = 30
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "-" * (bar_length - filled)

        print(f"\r[INFO] Scanning: |{bar}| {percent:.2f}%", end="", flush=True)

        if percent >= 100:
            break

        time.sleep(0.2)

    print()

# main.py

import threading
import time
from pathlib import Path

from config import DEFAULT_THREAD_COUNT, OUTPUT_FOLDER_NAME, TOOL_NAME, TOOL_VERSION
from signatures import get_signatures, get_supported_filetypes
from drive_utils import (
    is_admin,
    get_available_drives,
    validate_drive_letter,
    get_drive_size,
    get_raw_drive_path,
)
from utils import create_output_structure, format_size, get_timestamp
from scanner import RecoveryThread
from progress import progress_monitor
from report import generate_text_report, generate_json_report


def show_header():
    print("=" * 80)
    print(f"{TOOL_NAME} v{TOOL_VERSION} - Signature Based Data Recovery Tool")
    print("[INFO] Prototype for signature-based raw file carving and recovery")
    print("=" * 80)


def show_filetype_summary(file_counts):
    if file_counts:
        print("[INFO] Recovery summary by type:")
        for filetype, count in file_counts.items():
            print(f"   - {filetype.upper()}: {count}")
    else:
        print("[INFO] No recoverable files were saved.")


def main():
    show_header()

    if not is_admin():
        print("[INFO] Administrator privileges not detected.")
        print("[INFO] Some systems may restrict RAW recovery operations.\n")

    available_drives = get_available_drives()
    print("[INFO] Available drives:", available_drives)

    letter = input("Enter drive letter (or 'exit'): ").strip().upper()
    if letter == "EXIT":
        print("[INFO] Exiting...")
        return

    if not validate_drive_letter(letter):
        print("[ERROR] Invalid drive letter.")
        return

    try:
        total_size, mode = get_drive_size(letter)
        print(f"[INFO] Drive size         : {format_size(total_size)}")
        print(f"[INFO] Access mode        : {mode}")

        if mode != "RAW":
            print("[ERROR] RAW mode is required for full recovery. Run as administrator.")
            return

        drive_path = get_raw_drive_path(letter)
        signatures = get_signatures()
        supported_types = get_supported_filetypes()

        output_dir = Path.cwd() / OUTPUT_FOLDER_NAME
        folders = create_output_structure(output_dir, supported_types)

        print(f"[INFO] Output folder      : {folders['base']}")
        print(f"[INFO] Supported types    : {supported_types}")
        print(f"[INFO] Drive path         : {drive_path}")

        num_threads = DEFAULT_THREAD_COUNT
        chunk_size = total_size // num_threads

        processed_state = {"bytes": 0}
        recovery_state = {
            "files": [],
            "counts": {},
            "saved_offsets": set(),
        }

        lock = threading.Lock()
        threads = []

        print("\n[INFO] Starting scan...\n")
        start_time = time.time()

        for i in range(num_threads):
            start_offset = i * chunk_size
            end_offset = total_size if i == num_threads - 1 else (i + 1) * chunk_size

            thread = RecoveryThread(
                name=f"T{i+1}",
                start_offset=start_offset,
                end_offset=end_offset,
                drive_path=drive_path,
                signatures=signatures,
                output_folders=folders,
                total_size=total_size,
                processed_state=processed_state,
                lock=lock,
                recovery_state=recovery_state,
            )
            threads.append(thread)

        monitor_thread = threading.Thread(
            target=progress_monitor,
            args=(total_size, processed_state, lock),
            daemon=True
        )

        monitor_thread.start()

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        with lock:
            processed_state["bytes"] = total_size

        monitor_thread.join()

        end_time = time.time()
        time_taken = f"{end_time - start_time:.2f} seconds"

        print("\n" + "=" * 60)
        print("[DONE] Scan completed successfully")
        print(f"[INFO] Time taken        : {time_taken}")
        print(f"[INFO] Files recovered   : {len(recovery_state['files'])}")
        show_filetype_summary(recovery_state["counts"])

        report_data = {
            "timestamp": get_timestamp(),
            "tool_name": "DriveSift",
            "drive_letter": letter,
            "drive_path": drive_path,
            "drive_size": format_size(total_size),
            "mode": mode,
            "threads": num_threads,
            "time_taken": time_taken,
            "total_recovered": len(recovery_state["files"]),
            "file_counts": recovery_state["counts"],
            "recovered_files": recovery_state["files"],
            "limitations": [
                "Prototype implementation based on signature carving",
                "Best suited for non-fragmented files",
                "Currently stable for PDF, PNG, ZIP, and GIF formats",
            ],
        }

        text_report = generate_text_report(report_data, folders["reports"])
        json_report = generate_json_report(report_data, folders["reports"])

        print(f"[INFO] Text report       : {text_report}")
        print(f"[INFO] JSON report       : {json_report}")
        print("=" * 60)

    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()

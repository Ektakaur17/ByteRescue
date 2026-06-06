# report.py

import json
from pathlib import Path
from utils import get_timestamp, write_text_file, write_json_metadata


def generate_text_report(report_data, report_folder):
    report_folder = Path(report_folder)
    report_folder.mkdir(parents=True, exist_ok=True)

    timestamp   = get_timestamp()
    report_path = report_folder / f"scan_report_{timestamp}.txt"

    lines = [
        "BYTERESCUE — SCAN REPORT",
        "=" * 60,
        f"Tool              : {report_data.get('tool_name', 'N/A')}",
        f"Timestamp         : {report_data.get('timestamp', 'N/A')}",
        f"Drive Letter      : {report_data.get('drive_letter', 'N/A')}",
        f"Drive Size        : {report_data.get('drive_size', 'N/A')}",
        f"Access Mode       : {report_data.get('mode', 'N/A')}",
        f"Threads Used      : {report_data.get('threads', 'N/A')}",
        f"Time Taken        : {report_data.get('time_taken', 'N/A')}",
        f"Total Recovered   : {report_data.get('total_recovered', 0)}",
        "",
        "RECOVERY BY TYPE",
        "-" * 60,
    ]

    for ftype, count in report_data.get("file_counts", {}).items():
        lines.append(f"  {ftype.upper():12} : {count}")

    lines += ["", "RECOVERED FILES", "-" * 60]
    for i, f in enumerate(report_data.get("recovered_files", []), 1):
        lines.append(f"  {i:4}. {f}")

    lines += ["", "=" * 60, "END OF REPORT"]
    write_text_file(report_path, "\n".join(lines))
    return report_path


def generate_json_report(report_data, report_folder):
    report_folder = Path(report_folder)
    report_folder.mkdir(parents=True, exist_ok=True)

    timestamp   = get_timestamp()
    report_path = report_folder / f"scan_report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    return report_path


def generate_metadata_files(folders):
    """
    Write per-filetype JSON metadata files.
    e.g. Recovered_Files/images/jpg/jpg.json
    """
    write_json_metadata(folders)

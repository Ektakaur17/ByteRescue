# utils.py

import json
import threading
from pathlib import Path
from datetime import datetime
from forensic_logger import get_category, generate_filename, update_json_metadata, BASE_OUTPUT_DIR


# ═══════════════════════════════════════════════════════════════
#  CATEGORY MAPPING
# ═══════════════════════════════════════════════════════════════

CATEGORY_MAP = {
    "compressed": ["zip", "rar", "7z", "gz", "iso", "apk", "img", "tar"],
    "documents":  ["pdf", "doc", "docx", "xls", "xlsx", "csv",
                   "ppt", "pptx", "accdb", "pst", "ost"],
    "images":     ["jpg", "jpeg", "png", "gif", "tiff", "spool"],
    "videos":     ["mp4", "avi", "h264", "h265", "mkv", "mov", "flv"],
    "audio":      ["mp3", "wav", "aac"],
}


# ═══════════════════════════════════════════════════════════════
#  FOLDER STRUCTURE
#  Recovered_Files/
#    compressed/zip/
#    documents/pdf/
#    images/jpg/
#    videos/mp4/
#    audio/mp3/
# ═══════════════════════════════════════════════════════════════

def create_output_structure(base_output_dir, supported_types):
    base = Path(BASE_OUTPUT_DIR) # Force forensic logger's structure
    base.mkdir(parents=True, exist_ok=True)

    folders = {"base": base}

    # Per-filetype recovery folders now map deeply: Recovered_Files/images/jpg/
    for filetype in supported_types:
        category = get_category(filetype)
        file_dir = base / category / filetype
        file_dir.mkdir(parents=True, exist_ok=True)
        folders[filetype] = file_dir

    reports = base / "reports"
    reports.mkdir(exist_ok=True)
    folders["reports"] = reports

    return folders


# ═══════════════════════════════════════════════════════════════
#  FILE NAMING  — carved_file1.pdf, carved_file2.pdf ...
# ═══════════════════════════════════════════════════════════════

def generate_recovered_filename(filetype, offset=0,
                                 drive_path=None, file_size=None):
    """
    image1.jpg / document1.pdf / video1.mp4 / compressed1.zip / audio1.mp3
    """
    category = get_category(filetype)
    return generate_filename(category, filetype)


# ═══════════════════════════════════════════════════════════════
#  SECTOR CALCULATION
#  Sector size = 512 bytes (standard)
# ═══════════════════════════════════════════════════════════════

SECTOR_SIZE = 512


def offset_to_sector(offset):
    """Convert byte offset to sector number."""
    return offset // SECTOR_SIZE


def size_to_sectors(size_bytes):
    """Convert size in bytes to number of sectors."""
    return (size_bytes + SECTOR_SIZE - 1) // SECTOR_SIZE


# ═══════════════════════════════════════════════════════════════
#  JSON METADATA
#  Each filetype gets its own json file inside its folder
#  Format: [ { file_name, start_sector, end_sector }, ... ]
# ═══════════════════════════════════════════════════════════════

def reset_metadata():
    pass # No longer needed since forensic logger appends safely

def register_metadata(filetype, file_name, start_offset, end_offset):
    """
    Delegates metadata logging directly to forensic logger!
    Triggered on-the-fly during file carving!
    """
    update_json_metadata(filetype, file_name, start_offset, end_offset)


def write_json_metadata(json_dir):
    """
    Legacy sync point. No longer used because we write immediately.
    """
    return []


def get_metadata_summary():
    """Return copy of all metadata for report generation."""
    return {}


# ═══════════════════════════════════════════════════════════════
#  MISC HELPERS
# ═══════════════════════════════════════════════════════════════

def format_size(size_in_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    size  = float(size_in_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024


def format_offset(offset):
    return f"0x{offset:X}"


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def write_text_file(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

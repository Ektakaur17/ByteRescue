import os
import json
import threading
from pathlib import Path

# ==============================================================================
# CONFIGURATION & MAPPING
# ==============================================================================

BASE_OUTPUT_DIR = "Recovered_Files"
SECTOR_SIZE = 512

CATEGORY_MAP = {
    "images":     ["jpg", "jpeg", "png", "gif", "tiff", "bmp", "ico"],
    "documents":  ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "pst"],
    "compressed": ["zip", "rar", "7z", "gz", "tar", "iso"],
    "videos":     ["mp4", "avi", "mkv", "mov", "flv", "wmv"],
    "audio":      ["mp3", "wav", "m4a", "flac"]
}

CATEGORY_PREFIX = {
    "images":     "image",
    "documents":  "document",
    "compressed": "compressed",
    "videos":     "video",
    "audio":      "audio",
}

# Thread safety for concurrent file recovery
_log_lock = threading.Lock()
_file_counters = {}
_counters_lock = threading.Lock()

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_category(extension: str) -> str:
    """Returns the corresponding category for a given file extension."""
    ext_lower = extension.lower()
    for category, extensions in CATEGORY_MAP.items():
        if ext_lower in extensions:
            return category
    return "misc"

def generate_filename(category: str, extension: str) -> str:
    """
    Generates a sequential filename based on the category.
    Example: 'image1.jpg', 'image2.jpg', 'document1.pdf'
    """
    ext_lower = extension.lower()
    prefix = CATEGORY_PREFIX.get(category, "file")
    
    with _counters_lock:
        _file_counters[ext_lower] = _file_counters.get(ext_lower, 0) + 1
        count = _file_counters[ext_lower]
        
    return f"{prefix}{count}.{ext_lower}"

def setup_category_folder(category: str, extension: str) -> Path:
    """Ensures the directory for the given category and extension exists."""
    folder_path = Path(BASE_OUTPUT_DIR) / category / extension.lower()
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

# ==============================================================================
# CORE LOGGING FUNCTION
# ==============================================================================

def update_json_metadata(extension: str, file_name: str, start_offset: int, end_offset: int) -> None:
    """
    Updates the JSON metadata file for the given extension.
    Ensures thread safety and proper JSON array appending.
    """
    category = get_category(extension)
    folder_path = setup_category_folder(category, extension)
    json_file_path = folder_path / f"{extension.lower()}.json"

    new_entry = {
        "file_name": file_name,
        "exact_start_hex_offset": hex(start_offset).upper().replace("0X", "0x"),
        "exact_start_byte_offset": start_offset,
        "exact_end_hex_offset": hex(end_offset).upper().replace("0X", "0x"),
        "exact_end_byte_offset": end_offset,
        "approx_sector_number": start_offset // SECTOR_SIZE
    }

    with _log_lock:
        # Load existing data if file exists
        data = []
        if json_file_path.exists():
            try:
                with open(json_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[WARN] Failed to read existing JSON {json_file_path}: {e}. Overwriting.")
                data = []

        # Append new entry and save
        data.append(new_entry)

        try:
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"[ERROR] Failed to write JSON metadata to {json_file_path}: {e}")

# ==============================================================================
# INTEGRATION API
# ==============================================================================

def log_recovered_file(extension: str, start_offset: int, end_offset: int) -> str:
    """
    Main hook for integration.
    Generates filename, logs metadata to JSON, and returns the generated filename.
    
    WARNING: Call this immediately AFTER successful carving.
    """
    category = get_category(extension)
    file_name = generate_filename(category, extension)
    
    update_json_metadata(extension, file_name, start_offset, end_offset)
    
    return file_name

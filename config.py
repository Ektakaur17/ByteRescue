# config.py

"""
Configuration settings for the ByteRescue data recovery tool.
"""

# ---------------- BASIC SETTINGS ----------------

SCAN_CHUNK_SIZE     = 1 * 1024 * 1024    # 1 MB  (was 4 KB — major throughput gain)
THREAD_OVERLAP      = 2 * 1024 * 1024    # 2 MB  (kept larger than max signature window)
MAX_RECOVERY_FILE_SIZE = 200 * 1024 * 1024   # 200 MB cap for documents / images
MAX_VIDEO_SIZE         = 500 * 1024 * 1024   # 500 MB cap for video  (was hardcoded 100 MB)

DEFAULT_THREAD_COUNT = 4                 # was 2; 4 utilises modern NVMe better

OUTPUT_FOLDER_NAME  = "RecoveredData"
REPORTS_FOLDER_NAME = "reports"
TOOL_NAME           = "ByteRescue"
TOOL_VERSION        = "1.0"

# ---------------- FILE SIGNATURES ----------------
# start        = byte pattern to search for (used by chunk.find())
# end          = footer pattern (None for container-format videos)
# end_offset   = how many bytes past the footer to include
# NOTE: MP4 — we search for the literal "ftyp" atom marker.
#       The validator (is_valid_signature) checks for the 4-byte size prefix
#       that always precedes "ftyp" in a valid ISO Base Media file, so the
#       search key and the validation key are now consistent.

FILE_SIGNATURES = {

    # -------- IMAGES --------
    "jpg": {
        "start":      b"\xff\xd8\xff",
        "end":        b"\xff\xd9",
        "end_offset": 2,
    },
    "png": {
        "start":      b"\x89PNG\r\n\x1a\n",
        "end":        b"IEND\xaeB`\x82",
        "end_offset": 8,
    },

    # -------- DOCUMENTS --------
    "pdf": {
        "start":      b"%PDF",
        "end":        b"%%EOF",
        # Extra tail: linearised / signed PDFs have data after %%EOF.
        # 1 024 bytes of headroom captures trailing cross-reference tables.
        "end_offset": 1024,
    },

    # -------- VIDEOS & OTHERS --------
    "mp4": {
        "start":      b"ftyp",
        "end":        None,
        "end_offset": 0,
    },
    "avi": {
        "start":      b"RIFF",
        "end":        None,
        "end_offset": 0,
    },
    "mkv": {
        "start":      b"\x1A\x45\xDF\xA3",
        "end":        None,
        "end_offset": 0,
    },
    "mov": {
        "start":      b"moov",
        "end":        None,
        "end_offset": 0,
    },
    "flv": {
        "start":      b"FLV",
        "end":        None,
        "end_offset": 0,
    },
    "docx": {
        "start":      b"PK\x03\x04",
        "end":        b"PK\x05\x06",
        "end_offset": 22,
    },
}

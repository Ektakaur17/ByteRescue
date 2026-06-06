# signatures.py

"""
File signatures (magic numbers) for signature-based file recovery.
scanner.py is kO import karta hai - config.py ke FILE_SIGNATURES se sync hai.
"""

SIGNATURES = {

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
        "end_offset": 1024,
    },
    "zip": {
        "start":      b"PK\x03\x04",
        "end":        b"PK\x05\x06",
        "end_offset": 22,
    },
    "gif": {
        "start":      b"GIF8",
        "end":        b"\x3B",
        "end_offset": 1,
    },

    # -------- VIDEOS (end=None, atom/size based recovery) --------
    "mp4": {
        # "ftyp" atom name dhundh te hain
        # is_valid_signature() mein 4 bytes peeche ka box_size check hota hai
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
        # "moov" atom dhundh te hain
        # is_valid_signature() box_size validate karta hai
        "start":      b"moov",
        "end":        None,
        "end_offset": 0,
    },
    "flv": {
        "start":      b"FLV\x01",
        "end":        None,
        "end_offset": 0,
    },
}


def get_signatures():
    return SIGNATURES


def get_supported_filetypes():
    return list(SIGNATURES.keys())


def get_signature(filetype):
    return SIGNATURES.get(filetype.lower())


def is_supported_filetype(filetype):
    return filetype.lower() in SIGNATURES

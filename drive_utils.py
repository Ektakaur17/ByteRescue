# drive_utils.py

import os
import ctypes
import shutil


def is_admin():
    """
    Checks whether the current program is running with administrator privileges.

    Returns:
        bool: True if admin, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_available_drives():
    """
    Returns a list of available drive letters on the system.

    Returns:
        list[str]: Example -> ['C', 'D', 'E']
    """
    drives = []
    for letter in range(65, 91):  # ASCII A-Z
        drive_letter = chr(letter)
        if os.path.exists(f"{drive_letter}:"):
            drives.append(drive_letter)
    return drives


def get_raw_drive_path(letter):
    """
    Converts a drive letter into Windows RAW drive path format.

    Args:
        letter (str): Drive letter like 'C' or 'D'

    Returns:
        str: RAW path like '\\\\.\\C:'
    """
    letter = letter.upper().strip()
    return f"\\\\.\\{letter}:"


def validate_drive_letter(letter):
    """
    Validates whether the entered drive letter exists on the system.

    Args:
        letter (str): Drive letter entered by user

    Returns:
        bool: True if valid, False otherwise
    """
    if not letter or len(letter.strip()) != 1:
        return False

    letter = letter.upper().strip()
    return letter in get_available_drives()


def get_drive_size(letter):
    """
    Gets the total size of a drive using RAW access.
    Falls back to logical mode if RAW access fails.

    Args:
        letter (str): Drive letter like 'C'

    Returns:
        tuple: (total_size_in_bytes, mode)
               mode can be 'RAW' or 'LOGICAL'

    Raises:
        Exception: If drive cannot be accessed
    """
    letter = letter.upper().strip()

    try:
        drive = get_raw_drive_path(letter)

        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        FILE_FLAG_NO_BUFFERING = 0x20000000

        handle = ctypes.windll.kernel32.CreateFileW(
            drive,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_NO_BUFFERING,
            None
        )

        if handle in (-1, 0):
            raise Exception("RAW drive access failed")

        class GET_LENGTH_INFORMATION(ctypes.Structure):
            _fields_ = [("Length", ctypes.c_longlong)]

        length_info = GET_LENGTH_INFORMATION()
        bytes_returned = ctypes.c_ulong(0)

        IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C

        result = ctypes.windll.kernel32.DeviceIoControl(
            handle,
            IOCTL_DISK_GET_LENGTH_INFO,
            None,
            0,
            ctypes.byref(length_info),
            ctypes.sizeof(length_info),
            ctypes.byref(bytes_returned),
            None
        )

        ctypes.windll.kernel32.CloseHandle(handle)

        if result != 0:
            return length_info.Length, "RAW"

    except Exception:
        pass

    # Fallback to logical mode
    try:
        total, _, _ = shutil.disk_usage(f"{letter}:\\")
        return total, "LOGICAL"
    except Exception as exc:
        raise Exception(f"Unable to access drive {letter}: {exc}")


def can_access_raw_drive(letter):
    """
    Checks if RAW access is possible for a given drive.

    Args:
        letter (str): Drive letter

    Returns:
        bool: True if RAW access works, else False
    """
    try:
        _, mode = get_drive_size(letter)
        return mode == "RAW"
    except Exception:
        return False

# scanner.py

from pathlib import Path
import struct

from config import (
    SCAN_CHUNK_SIZE, THREAD_OVERLAP,
    MAX_RECOVERY_FILE_SIZE, MAX_VIDEO_SIZE,
)
from utils import (
    generate_recovered_filename, format_offset,
    register_metadata, offset_to_sector, SECTOR_SIZE,
)


# ─────────────────────────────────────────────────────────────────
#  Per-type seek-back adjustments
#  MP4/MOV: we search "ftyp" atom name; real file starts 4 bytes
#  earlier (the box-size field).
# ─────────────────────────────────────────────────────────────────
RECOVERY_REWIND = {
    "mp4": 4,
    "mov": 4,
}


class RecoveryThread(__import__("threading").Thread):

    def __init__(
        self,
        name, start_offset, end_offset,
        drive_path, signatures, output_folders,
        total_size, processed_state, lock, recovery_state,
        log_callback=None, file_found_callback=None,
    ):
        super().__init__(name=name)
        self.start_offset        = start_offset
        self.end_offset          = end_offset
        self.drive_path          = drive_path
        self.signatures          = signatures
        self.output_folders      = output_folders
        self.total_size          = total_size
        self.processed_state     = processed_state
        self.lock                = lock
        self.recovery_state      = recovery_state
        self.chunk_size          = SCAN_CHUNK_SIZE
        self.overlap             = THREAD_OVERLAP
        self.log_callback        = log_callback
        self.file_found_callback = file_found_callback

        self._max_sig_len = max(
            len(sig["start"])
            for sig in signatures.values()
            if isinstance(sig.get("start"), bytes)
        )

    # ──────────────────────────────────────────────────────────────
    #  LOGGING
    # ──────────────────────────────────────────────────────────────
    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    # ──────────────────────────────────────────────────────────────
    #  MAIN RUN LOOP
    # ──────────────────────────────────────────────────────────────
    def run(self):
        scan_start = max(0, self.start_offset - self.overlap)
        scan_end   = min(self.total_size, self.end_offset + self.overlap)

        try:
            with open(self.drive_path, "rb") as drive:
                offset = scan_start
                tail   = b""

                while offset < scan_end:
                    try:
                        drive.seek(offset)
                        raw_chunk = drive.read(self.chunk_size)
                    except Exception as exc:
                        self.log(f"[ERROR] Read at {format_offset(offset)}: {exc}")
                        break

                    if not raw_chunk:
                        break

                    chunk = tail + raw_chunk

                    # Progress accounting
                    r_start = max(self.start_offset, offset)
                    r_end   = min(self.end_offset, offset + len(raw_chunk))
                    if r_end > r_start:
                        with self.lock:
                            self.processed_state["bytes"] += r_end - r_start

                    self.scan_chunk(chunk, offset - len(tail))

                    tail    = raw_chunk[-self._max_sig_len:]
                    offset += len(raw_chunk)

        except Exception as exc:
            self.log(f"[CRITICAL] Thread {self.name}: {exc}")

    # ──────────────────────────────────────────────────────────────
    #  SIGNATURE VALIDATION
    # ──────────────────────────────────────────────────────────────
    def is_valid_signature(self, filetype, chunk, pos):
        try:
            if filetype == "png":
                return chunk[pos:pos+8] == b"\x89PNG\r\n\x1a\n"

            if filetype in ("jpg", "jpeg"):
                return (chunk[pos:pos+3] == b"\xff\xd8\xff"
                        and len(chunk) > pos+3
                        and chunk[pos+3] in (0xE0, 0xE1, 0xE8, 0xDB, 0xFE))

            if filetype == "pdf":
                return chunk[pos:pos+4] == b"%PDF"

            if filetype in ("zip", "docx"):
                if chunk[pos:pos+4] != b"PK\x03\x04":
                    return False
                if len(chunk) < pos+6:
                    return True
                ver = struct.unpack("<H", chunk[pos+4:pos+6])[0]
                return ver <= 63

            if filetype == "gif":
                return chunk[pos:pos+6] in (b"GIF87a", b"GIF89a")

            if filetype == "mp4":
                if pos < 4:
                    return False
                box_size = int.from_bytes(chunk[pos-4:pos], "big")
                if not (8 <= box_size <= 512):
                    return False
                if chunk[pos:pos+4] != b"ftyp":
                    return False
                brand = chunk[pos+4:pos+8]
                return len(brand) == 4 and all(0x20 <= b < 0x7F for b in brand)

            if filetype == "avi":
                return (len(chunk) >= pos+12
                        and chunk[pos:pos+4] == b"RIFF"
                        and chunk[pos+8:pos+12] == b"AVI ")

            if filetype in ("doc", "xls", "ppt"):
                return chunk[pos:pos+8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

            if filetype in ("docx", "xlsx", "pptx", "zip", "apk"):
                return chunk[pos:pos+4] == b"PK\x03\x04"

            if filetype == "rar":
                return chunk[pos:pos+6] == b"Rar!\x1a\x07"

            if filetype == "7z":
                return chunk[pos:pos+6] == b"7z\xbc\xaf'\x1c"

            if filetype == "gz":
                return chunk[pos:pos+3] == b"\x1f\x8b\x08"

            if filetype == "mp3":
                return chunk[pos:pos+3] == b"ID3"

            if filetype == "tiff":
                return chunk[pos:pos+4] in (b"II*\x00", b"MM\x00*")

            if filetype == "pst":
                return chunk[pos:pos+4] == b"!BDN"

            return True

        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────
    #  SCAN CHUNK
    # ──────────────────────────────────────────────────────────────
    def scan_chunk(self, chunk, chunk_disk_base):
        for filetype, sig in self.signatures.items():
            start_sig = sig.get("start")
            if not isinstance(start_sig, bytes):
                continue

            end_sig          = sig["end"]
            end_offset_bytes = sig["end_offset"]
            search_pos       = 0

            while True:
                found_at = chunk.find(start_sig, search_pos)
                if found_at == -1:
                    break

                if len(chunk) - found_at < 20:
                    search_pos = found_at + 1
                    continue

                if not self.is_valid_signature(filetype, chunk, found_at):
                    search_pos = found_at + 1
                    continue

                sig_offset  = chunk_disk_base + found_at
                rewind      = RECOVERY_REWIND.get(filetype, 0)
                real_offset = sig_offset - rewind

                if real_offset < 0 or real_offset >= self.total_size:
                    search_pos = found_at + 1
                    continue

                if self.start_offset <= sig_offset <= self.end_offset:
                    sector = offset_to_sector(real_offset)
                    self.log(
                        f"[FOUND] {filetype.upper()} at {format_offset(real_offset)}"
                        f"  (sector {sector})"
                        + (f"  atom@{format_offset(sig_offset)}" if rewind else "")
                    )
                    try:
                        self.recover_file(
                            filetype, real_offset,
                            end_sig, end_offset_bytes
                        )
                    except Exception as exc:
                        self.log(f"[ERROR] {filetype} @ {format_offset(real_offset)}: {exc}")

                search_pos = found_at + 1

    # ──────────────────────────────────────────────────────────────
    #  RECOVERY ENTRY POINT
    # ──────────────────────────────────────────────────────────────
    def recover_file(self, filetype, start_offset, end_sig, end_offset_bytes):
        if start_offset < 0 or start_offset >= self.total_size:
            return

        with self.lock:
            if start_offset in self.recovery_state["saved_offsets"]:
                return
            self.recovery_state["saved_offsets"].add(start_offset)

        output_folder = self.output_folders.get(filetype)
        if not output_folder:
            self.log(f"[WARN] No folder for {filetype}")
            return

        filename    = generate_recovered_filename(filetype, start_offset)
        output_path = Path(output_folder) / filename

        try:
            with open(self.drive_path, "rb") as drive:
                try:
                    drive.seek(start_offset)
                except Exception:
                    self.log(f"[SKIP] Bad offset {format_offset(start_offset)}")
                    with self.lock:
                        self.recovery_state["saved_offsets"].discard(start_offset)
                    return

                if end_sig is None:
                    self._recover_video(
                        drive, filetype, start_offset,
                        output_path, filename
                    )
                else:
                    self._recover_normal(
                        drive, filetype, start_offset,
                        end_sig, end_offset_bytes,
                        output_path, filename,
                    )

        except Exception as exc:
            self.log(f"[CRITICAL] Recovery failed {filename}: {exc}")

    # ──────────────────────────────────────────────────────────────
    #  VIDEO / CONTAINER RECOVERY (no footer)
    # ──────────────────────────────────────────────────────────────
    def _recover_video(self, drive, filetype, start_offset,
                       output_path, filename):

        if filetype == "mp4":
            self._recover_mp4_atoms(start_offset, output_path, filename)
            return

        if filetype == "avi":
            self._recover_avi_riff(drive, start_offset, output_path, filename)
            return

        # Generic: sector-boundary heuristic for mkv, flv, mp3, rar, 7z etc.
        self._recover_heuristic(
            drive, filetype, start_offset, output_path, filename
        )

    # ──────────────────────────────────────────────────────────────
    #  MP4 — atom walk
    # ──────────────────────────────────────────────────────────────
    def _recover_mp4_atoms(self, start_offset, output_path, filename):
        from mp4_recovery import MP4Recovery

        ftyp_offset = start_offset + 4
        recoverer   = MP4Recovery(
            drive_path=self.drive_path,
            output_path=output_path.parent,
        )

        real_start, file_size = recoverer.find_boundaries(ftyp_offset)
        result = recoverer.recover(ftyp_offset)

        if result:
            result_path = Path(result)
            if result_path.exists() and result_path != output_path:
                result_path.rename(output_path)

            end_offset = start_offset + (file_size or 0)
            register_metadata(
                "mp4", filename,
                start_offset, end_offset
            )
            self.log(f"[SAVED MP4] {filename}")
            self._register_saved("mp4", str(output_path))
        else:
            self.log(f"[WARN] MP4 atom walk failed @ {format_offset(start_offset)}")
            try:
                with open(self.drive_path, "rb") as drive:
                    drive.seek(start_offset)
                    self._recover_heuristic(
                        drive, "mp4", start_offset, output_path, filename
                    )
            except Exception as e:
                self.log(f"[ERROR] MP4 fallback: {e}")

    # ──────────────────────────────────────────────────────────────
    #  AVI — RIFF size header
    # ──────────────────────────────────────────────────────────────
    def _recover_avi_riff(self, drive, start_offset, output_path, filename):
        try:
            drive.seek(start_offset + 4)
            raw = drive.read(4)
            if len(raw) < 4:
                raise ValueError("Cannot read RIFF size")

            riff_data_size = struct.unpack("<I", raw)[0]
            total_size     = riff_data_size + 8

            if not (100 < total_size <= MAX_VIDEO_SIZE):
                raise ValueError(f"Unreasonable AVI size {total_size}")

            drive.seek(start_offset)
            remaining = total_size

            with open(output_path, "wb") as out:
                while remaining > 0:
                    chunk = drive.read(min(self.chunk_size, remaining))
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)

            end_offset = start_offset + total_size
            register_metadata("avi", filename, start_offset, end_offset)
            self.log(f"[SAVED AVI] {filename} ({total_size//1024} KB)")
            self._register_saved("avi", str(output_path))

        except Exception as e:
            self.log(f"[WARN] AVI RIFF failed: {e} — heuristic fallback")
            drive.seek(start_offset)
            self._recover_heuristic(
                drive, "avi", start_offset, output_path, filename
            )

    # ──────────────────────────────────────────────────────────────
    #  HEURISTIC — sector-boundary next-signature stop
    # ──────────────────────────────────────────────────────────────
    def _recover_heuristic(self, drive, filetype, start_offset,
                            output_path, filename):
        SECTOR     = SECTOR_SIZE
        data_parts = []
        total_read = 0

        while total_read < MAX_VIDEO_SIZE:
            chunk = drive.read(self.chunk_size)
            if not chunk:
                break

            stop_pos  = len(chunk)
            stop_flag = False

            for other_type, other_sig in self.signatures.items():
                if other_type == filetype:
                    continue
                sig_bytes = other_sig.get("start")
                if not isinstance(sig_bytes, bytes):
                    continue
                pos = chunk.find(sig_bytes)
                while pos != -1:
                    disk_pos = start_offset + total_read + pos
                    if disk_pos % SECTOR == 0 and pos > 0:
                        if pos < stop_pos:
                            stop_pos = pos
                        stop_flag = True
                        break
                    pos = chunk.find(sig_bytes, pos+1)
                if stop_flag:
                    break

            data_parts.append(chunk[:stop_pos])
            total_read += stop_pos

            if stop_flag:
                break

        if total_read < 8:
            self.log(f"[WARN] {filename} too small — skipping")
            with self.lock:
                self.recovery_state["saved_offsets"].discard(start_offset)
            return

        with open(output_path, "wb") as out:
            for part in data_parts:
                out.write(part)

        end_offset = start_offset + total_read
        register_metadata(filetype, filename, start_offset, end_offset)
        self.log(f"[SAVED] {filename} ({total_read//1024} KB)")
        self._register_saved(filetype, str(output_path))

    # ──────────────────────────────────────────────────────────────
    #  NORMAL — footer-terminated (PDF, PNG, JPG, ZIP, GIF …)
    # ──────────────────────────────────────────────────────────────
    def _recover_normal(self, drive, filetype, start_offset,
                        end_sig, end_offset_bytes,
                        output_path, filename):
        chunks     = []
        total_read = 0
        found      = False
        final_data = b""

        while total_read < MAX_RECOVERY_FILE_SIZE:
            chunk = drive.read(self.chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            total_read += len(chunk)

            window  = b"".join(chunks[-2:]) if len(chunks) >= 2 else chunks[-1]
            end_pos = window.find(end_sig)

            if end_pos != -1:
                tail_start = total_read - len(window)
                keep       = tail_start + end_pos + end_offset_bytes
                full       = b"".join(chunks)
                final_data = full[:keep]
                found      = True
                break

        if not found:
            final_data = b"".join(chunks)

        with open(output_path, "wb") as out:
            out.write(final_data)

        end_offset = start_offset + len(final_data)
        register_metadata(filetype, filename, start_offset, end_offset)

        if found:
            self.log(f"[SAVED] {filename} ({len(final_data)//1024} KB)")
        else:
            self.log(f"[PARTIAL] {filename} ({total_read//1024} KB)")

        self._register_saved(filetype, str(output_path))

    # ──────────────────────────────────────────────────────────────
    #  REGISTRATION
    # ──────────────────────────────────────────────────────────────
    def _register_saved(self, filetype, path_str):
        with self.lock:
            self.recovery_state["files"].append(path_str)
            self.recovery_state["counts"][filetype] = (
                self.recovery_state["counts"].get(filetype, 0) + 1
            )
        if self.file_found_callback:
            self.file_found_callback()

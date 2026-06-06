# mp4_recovery.py

from pathlib import Path
import struct

VALID_MP4_ATOMS = {
    b"ftyp", b"moov", b"mdat", b"free",
    b"skip", b"wide", b"pnot", b"udta",
    b"meta", b"trak", b"mdia", b"minf",
    b"stbl", b"edts", b"dinf", b"uuid",
    b"mvhd", b"tkhd", b"mdhd", b"hdlr",
    b"smhd", b"vmhd", b"stsd", b"stts",
    b"stsc", b"stsz", b"stco", b"ctts",
}

MAX_MP4_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB


class MP4Recovery:
    """
    Atom-based MP4/MOV recovery.
    Atoms walk karke file ka actual end dhundta hai.
    """

    def __init__(self, drive_path, output_path, chunk_size=1024 * 1024):
        # NOTE: __init__ - do underscores dono taraf (pehle _init_ tha - bug tha)
        self.drive_path  = drive_path
        self.output_path = Path(output_path)
        self.chunk_size  = chunk_size

    def _read_atom_header(self, f, offset):
        """
        Ek atom ka size aur name padho.

        MP4 atom structure:
        [4 bytes - big-endian size][4 bytes - atom name][...data...]

        Returns: (atom_name_bytes, size_int) ya (None, None) if invalid
        """
        try:
            f.seek(offset)
            header = f.read(8)
            if len(header) < 8:
                return None, None

            size = struct.unpack(">I", header[:4])[0]
            name = header[4:8]

            # size == 1 matlab next 8 bytes mein 64-bit extended size hai
            if size == 1:
                ext = f.read(8)
                if len(ext) < 8:
                    return None, None
                size = struct.unpack(">Q", ext)[0]

            # size == 0 matlab ye atom file ke end tak hai
            if size == 0:
                return name, None

            # Sanity check
            if size < 8 or size > MAX_MP4_SIZE:
                return None, None

            return name, size

        except Exception:
            return None, None

    def find_file_size(self, ftyp_offset):
        """
        ftyp atom ke offset se shuru karke atoms walk karo.
        Jab valid atom na mile tab file khatam samjho.

        Args:
            ftyp_offset: disk offset jahan 'ftyp' string mila tha

        Returns:
            Total file size in bytes, ya None if detection failed
        """
        # ftyp ke 4 bytes peeche jaao - wahan real file start hai (box size field)
        real_start      = ftyp_offset - 4
        current_offset  = real_start
        total_size      = 0

        try:
            with open(self.drive_path, "rb") as f:
                while True:
                    atom_name, atom_size = self._read_atom_header(f, current_offset)

                    if atom_name is None:
                        # Invalid atom - file yahan khatam
                        break

                    if atom_name not in VALID_MP4_ATOMS:
                        # Unknown atom - file end
                        break

                    if atom_size is None:
                        # size=0 case - reasonable chunk le lo aur band karo
                        total_size += self.chunk_size
                        break

                    total_size      += atom_size
                    current_offset  += atom_size

                    if total_size > MAX_MP4_SIZE:
                        print(f"[WARN] MP4 too large at 0x{ftyp_offset:X}, capping")
                        break

            return total_size if total_size > 0 else None

        except Exception as e:
            print(f"[ERROR] MP4 size detection failed at 0x{ftyp_offset:X}: {e}")
            return None

    def recover(self, ftyp_offset):
        """
        ftyp_offset pe MP4 recover karke file save karo.

        Args:
            ftyp_offset: disk offset jahan 'ftyp' signature mila tha

        Returns:
            Saved file path (str) ya None if failed
        """
        print(f"[INFO] MP4 atom-walk starting at 0x{ftyp_offset:X}")

        file_size  = self.find_file_size(ftyp_offset)
        real_start = ftyp_offset - 4

        if not file_size:
            print(f"[WARN] Could not determine MP4 size at 0x{ftyp_offset:X}")
            return None

        size_mb = file_size / (1024 * 1024)
        print(f"[INFO] Detected MP4 size: {size_mb:.2f} MB")

        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
            out_file = self.output_path / f"recovered_0x{real_start:X}.mp4"

            with open(self.drive_path, "rb") as f:
                f.seek(real_start)
                remaining = file_size

                with open(out_file, "wb") as out:
                    while remaining > 0:
                        to_read = min(self.chunk_size, remaining)
                        chunk   = f.read(to_read)
                        if not chunk:
                            break
                        out.write(chunk)
                        remaining -= len(chunk)

            print(f"[OK] MP4 saved: {out_file}")
            return str(out_file)

        except Exception as e:
            print(f"[ERROR] MP4 write failed at 0x{ftyp_offset:X}: {e}")
            return None

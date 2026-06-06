# ByteRescue
ByteRescue is a Python-based digital forensic file carving tool that recovers data directly from raw binary storage — bypassing FAT32, NTFS, and exFAT file systems entirely. It reads storage devices sector-by-sector, identifies known file signatures (magic bytes), and reconstructs files without needing any file system metadata. 
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" />
  <img src="https://img.shields.io/badge/License-Educational-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Version-1.0-00e5cc?style=for-the-badge" />
</p>

<h1 align="center">🔬 ByteRescue</h1>
<h3 align="center">Signature-Based File Carving & Forensic Recovery Tool</h3>

<p align="center">
  <i>Recover deleted, lost, or inaccessible files from storage media — even when the file system is completely destroyed.</i>
</p>

---

## 📖 Overview

**ByteRescue** is a Python-based digital forensic file carving tool that recovers data directly from raw binary storage — bypassing FAT32, NTFS, and exFAT file systems entirely. It reads storage devices sector-by-sector, identifies known file signatures (magic bytes), and reconstructs files without needing any file system metadata.

This technique is known in Digital Forensics as **File Carving** or **Raw Data Carving**.

> Whether your USB was quick-formatted, your SD card got corrupted, or your HDD's partition table was wiped — if the raw bytes are still on the disk, **ByteRescue can find them**.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 **Raw Disk Scanning** | Reads storage devices at the byte level, bypassing all file system layers |
| ⚡ **Multi-Threaded Engine** | 4 parallel scanner threads with 2MB overlap for boundary-safe recovery |
| 🎯 **Smart Signature Validation** | Multi-layer validation — not just header matching, but structural integrity checks |
| 🎬 **MP4 Atom Walker** | Specialized ISO Base Media Box parser for precise video file boundary detection |
| 📊 **Forensic JSON Logging** | Exact byte offset (decimal + hex) + sector number logged for every recovered file |
| 🖥️ **Military OSINT GUI** | Full Tkinter interface with radar sweep, glow bars, and live terminal log |
| 📝 **Auto Report Generation** | Text + JSON scan reports generated after every recovery session |
| 🗂️ **Category-Based Output** | Files auto-organized into `images/`, `documents/`, `videos/`, `compressed/` folders |
| 🔒 **Thread-Safe Deduplication** | Atomic offset tracking prevents the same file from being recovered twice |
| 📦 **Standalone EXE** | Can be packaged into a portable `.exe` via PyInstaller |

---

## 🗂️ Supported File Types

### Images
| Format | Signature (Hex) | Recovery Method |
|--------|-----------------|-----------------|
| **JPEG** (.jpg) | `FF D8 FF` | Footer-based (`FF D9`) |
| **PNG** (.png) | `89 50 4E 47 0D 0A 1A 0A` | Footer-based (`IEND`) |
| **GIF** (.gif) | `47 49 46 38` (GIF8) | Footer-based (`3B`) |

### Documents
| Format | Signature (Hex) | Recovery Method |
|--------|-----------------|-----------------|
| **PDF** (.pdf) | `25 50 44 46` (%PDF) | Footer-based (`%%EOF` + 1KB headroom) |
| **DOCX** (.docx) | `50 4B 03 04` (PK..) | Footer-based (ZIP EOCD) |
| **ZIP** (.zip) | `50 4B 03 04` (PK..) | Footer-based (ZIP EOCD) |

### Videos
| Format | Signature (Hex) | Recovery Method |
|--------|-----------------|-----------------|
| **MP4** (.mp4) | `66 74 79 70` (ftyp) | **Atom Walk** — ISO box structure parsing |
| **AVI** (.avi) | `52 49 46 46 .. AVI ` | **RIFF Header** — size field extraction |
| **MKV** (.mkv) | `1A 45 DF A3` | Heuristic (next-signature boundary) |
| **MOV** (.mov) | `6D 6F 6F 76` (moov) | Heuristic |
| **FLV** (.flv) | `46 4C 56 01` (FLV) | Heuristic |

### Archives & Others
| Format | Signature (Hex) | Recovery Method |
|--------|-----------------|-----------------|
| **RAR** (.rar) | `52 61 72 21 1A 07` | Heuristic |
| **7-Zip** (.7z) | `37 7A BC AF 27 1C` | Heuristic |
| **GZIP** (.gz) | `1F 8B 08` | Heuristic |
| **MP3** (.mp3) | `49 44 33` (ID3) | Heuristic |
| **TIFF** (.tiff) | `49 49 2A 00` / `4D 4D 00 2A` | Heuristic |

---

## 🏗️ Project Architecture

```
ByteRescue/
├── gui.py              ← Main GUI entry point (Military OSINT theme)
├── main.py             ← CLI entry point & scan orchestration
├── config.py           ← Global settings & file signatures dictionary
├── signatures.py       ← Active signature loader
├── scanner.py          ← Core carving engine (RecoveryThread class)
├── mp4_recovery.py     ← Specialized MP4 atom-walking recovery
├── drive_utils.py      ← Windows RAW disk access & drive enumeration
├── utils.py            ← Output structure, file naming, helpers
├── forensic_logger.py  ← JSON metadata logging system
├── progress.py         ← Live console progress monitor
├── report.py           ← Text & JSON scan report generation
├── generate_report.py  ← DOCX project report generator
├── ByteRescue.spec     ← PyInstaller packaging spec
└── requirements.txt    ← Python dependencies
```

### Module Responsibilities

| Module | Role |
|--------|------|
| `scanner.py` | Core engine — each `RecoveryThread` reads 1MB chunks with 2MB overlap, validates signatures, and dispatches to the correct recovery strategy |
| `mp4_recovery.py` | Walks ISO Base Media Box (Atom) structure — `ftyp → moov → mdat` — to determine exact MP4 file boundaries without a footer |
| `forensic_logger.py` | Thread-safe JSON metadata writer — records `file_name`, `exact_start_hex_offset`, `exact_end_hex_offset`, `approx_sector_number` |
| `drive_utils.py` | Uses `ctypes` + Windows Kernel32 API (`CreateFileW`, `DeviceIoControl`) for RAW disk handle access |
| `gui.py` | 1200+ line Tkinter GUI — animated radar sweep, glow progress bar, colour-coded log terminal, recovery summary cards |
| `config.py` | Central config — chunk sizes, thread count, max file sizes, and the master file signatures dictionary |

---

## ⚙️ How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                    ByteRescue Pipeline                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SELECT DRIVE      User picks target drive (E:, F:, etc.) │
│         │                                                    │
│  2. RAW ACCESS        \\.\E: opened via Kernel32 API         │
│         │              (bypasses file system entirely)       │
│         │                                                    │
│  3. PARTITION          Drive split into N equal chunks       │
│         │              (default: 4 threads, 2MB overlap)     │
│         │                                                    │
│  4. SCAN CHUNKS       chunk.find(signature) for all types   │
│         │              (C-level speed via Python internals)  │
│         │                                                    │
│  5. VALIDATE          is_valid_signature() checks structure  │
│         │              (not just header — deep validation)   │
│         │                                                    │
│  6. CARVE FILE        Strategy dispatched per file type:     │
│         │              • Footer-based (JPG, PDF, PNG, ZIP)   │
│         │              • Atom Walk (MP4)                     │
│         │              • RIFF Header (AVI)                   │
│         │              • Heuristic (MKV, FLV, RAR, 7z...)   │
│         │                                                    │
│  7. LOG METADATA      JSON entry written immediately        │
│         │              (thread-safe, per-type JSON files)    │
│         │                                                    │
│  8. REPORT            Text + JSON summary reports generated  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **Windows OS** (required for RAW disk access via Kernel32 API)
- **Administrator privileges** (required for `\\.\X:` raw device access)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ByteRescue.git
cd ByteRescue

# No external dependencies needed — runs on Python standard library!
# (python-docx required only for DOCX report generation)
pip install python-docx   # optional — for generate_report.py
```

### Running the Tool

#### 🖥️ GUI Mode (Recommended)

```bash
# Right-click → "Run as Administrator"
python gui.py
```

#### ⌨️ CLI Mode

```bash
# Run from an elevated (admin) command prompt
python main.py
```

#### 📦 Build Standalone EXE

```bash
pip install pyinstaller
pyinstaller ByteRescue.spec
# Output: dist/ByteRescue.exe
```

---

## 📂 Output Structure

After a scan, recovered files are organized into a structured directory:

```
Recovered_Files/
├── images/
│   ├── jpg/
│   │   ├── image1.jpg
│   │   ├── image2.jpg
│   │   └── jpg.json          ← Forensic metadata log
│   ├── png/
│   │   ├── image1.png
│   │   └── png.json
│   └── gif/
│       └── gif.json
├── documents/
│   ├── pdf/
│   │   ├── document1.pdf
│   │   └── pdf.json
│   └── docx/
│       ├── document1.docx
│       └── docx.json
├── videos/
│   ├── mp4/
│   │   ├── video1.mp4
│   │   └── mp4.json
│   └── avi/
│       └── avi.json
├── compressed/
│   └── zip/
│       └── zip.json
└── reports/
    ├── scan_report_2026-04-13.txt
    └── scan_report_2026-04-13.json
```

### Sample JSON Metadata (`jpg.json`)

```json
[
  {
    "file_name": "image1.jpg",
    "exact_start_hex_offset": "0x548000",
    "exact_start_byte_offset": 5537792,
    "exact_end_hex_offset": "0x923216",
    "exact_end_byte_offset": 9581078,
    "approx_sector_number": 10816
  }
]
```

> **Every offset is independently verifiable** — open your drive in HxD Hex Editor, press `Ctrl+G`, enter the hex offset, and you'll land exactly on the file's magic bytes.

---

## 🔧 Configuration

All tunable parameters are in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCAN_CHUNK_SIZE` | 1 MB | Read buffer size per iteration |
| `THREAD_OVERLAP` | 2 MB | Overlap between thread boundaries (prevents missed signatures) |
| `MAX_RECOVERY_FILE_SIZE` | 200 MB | Safety cap for documents & images |
| `MAX_VIDEO_SIZE` | 500 MB | Safety cap for video files |
| `DEFAULT_THREAD_COUNT` | 4 | Number of parallel scanner threads |
| `OUTPUT_FOLDER_NAME` | `RecoveredData` | Root folder for recovered files |

---

## 🔬 Forensic Validation

### Hex Editor Verification Procedure

1. Open **HxD Hex Editor**
2. Go to `File → Open Disk → Logical Disks → Select your drive`
3. Press `Ctrl+G` (Go To Offset)
4. Select **Hex** mode
5. Enter the `exact_start_hex_offset` from the JSON (e.g., `548000`)
6. ✅ Cursor lands exactly on the file's magic bytes (e.g., `FF D8 FF E0` for JPEG)

> This validates the forensic accuracy of ByteRescue's offset tracking system.

---

## 🧩 Recovery Strategies Explained

### 1. Footer-Based Recovery
Used for: **JPEG, PNG, GIF, PDF, ZIP, DOCX**

Reads from the header signature until the known footer pattern is found. For PDF, an extra 1024-byte headroom is added to capture trailing cross-reference tables in linearized/signed PDFs.

### 2. Atom Walk Recovery
Used for: **MP4**

MP4 files use ISO Base Media File Format — no footer exists. Instead, `mp4_recovery.py` walks the atom (box) structure:
```
[4-byte size][4-byte name → ftyp][data...]
[4-byte size][4-byte name → moov][data...]
[4-byte size][4-byte name → mdat][data...]
```
Each atom declares its own size. Walk atoms until an invalid one is found = file end.

### 3. RIFF Header Recovery
Used for: **AVI**

AVI files use RIFF container format. Bytes 4–7 contain the payload size as a little-endian 32-bit integer. Total file size = `payload_size + 8`.

### 4. Heuristic Recovery
Used for: **MKV, MOV, FLV, RAR, 7z, GZIP, MP3, TIFF**

Reads forward from the header until a *different* file signature is found at a sector-aligned boundary (512-byte aligned). This provides a reasonable approximation of the file end for container formats without footers.

---

## ⚠️ Limitations

- **Windows Only** — relies on Kernel32 API for RAW disk access
- **Non-Fragmented Files** — file carving works best when file data is stored contiguously on disk
- **Admin Required** — RAW device access (`\\.\X:`) requires elevated privileges
- **No Encrypted Volumes** — cannot recover from BitLocker/VeraCrypt encrypted partitions
- **Prototype Scope** — best suited for educational/forensic demonstration purposes

---

## 🔭 Future Scope

| Feature | Description |
|---------|-------------|
| 🤖 **AI Integration** | Feed JSON metadata to LLM APIs for automated forensic analysis reports |
| 💿 **Disk Image Support** | Scan `.dd`, `.img`, and `.E01` forensic image files |
| 📷 **More File Types** | RAW camera formats (.CR2, .NEF), SQLite databases, email archives |
| 📈 **Timeline View** | Graphical timeline of recovered files based on disk sector position |
| 🔐 **SHA-256 Hashing** | Per-file integrity hashing for chain-of-custody evidence |
| 🐧 **Cross-Platform** | Linux/macOS support via `/dev/sdX` raw device access |

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.x** | Core development language |
| **Tkinter** | Graphical User Interface |
| **threading** | Multi-threaded parallel scanning |
| **struct** | Binary data parsing (MP4 atoms, AVI RIFF) |
| **ctypes** | Windows Kernel32 API for raw disk access |
| **json** | Forensic metadata logging |
| **pathlib** | Cross-platform path management |
| **PyInstaller** | Standalone EXE packaging |

---

## 👥 Authors

**Harsh Belwal** & **Ekta Kaur**

> *Digital Forensics / Cyber Security Project*

---

## 📄 License

This project is developed for educational and research purposes in the field of Digital Forensics and Cyber Security.

---

<p align="center">
  <b>ByteRescue v1.0</b> — <i>When the file system fails, the bytes remain.</i>
</p>

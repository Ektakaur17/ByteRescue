# gui.py — ByteRescue | Classified Forensic Recovery Terminal
# Aesthetic: Military OSINT / Deep-scan terminal
# Fonts: Orbitron (display) + JetBrains Mono (mono) via local fallback chain

import threading
import os
import math
import time
import random
import struct
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from config import DEFAULT_THREAD_COUNT, OUTPUT_FOLDER_NAME, TOOL_NAME, TOOL_VERSION
from signatures import get_signatures, get_supported_filetypes
from drive_utils import (
    get_available_drives, validate_drive_letter,
    get_drive_size, get_raw_drive_path,
)
from utils import create_output_structure, get_timestamp
from scanner import RecoveryThread
from report import generate_text_report, generate_json_report


# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE  — Deep military forensics
# ═══════════════════════════════════════════════════════════════════════════════
P = {
    "void":        "#04070d",   # deepest background
    "bg":          "#080d14",   # main background
    "surface":     "#0c1420",   # raised surface
    "glass":       "#111c2e",   # glassmorphism panel
    "glass2":      "#162135",   # slightly lighter glass
    "rim":         "#1e3a5f",   # subtle border / rim
    "rim_hi":      "#2d5a8e",   # hover rim
    "orange":      "#ff6b1a",   # primary accent — blood orange
    "orange_dim":  "#8a3a0d",   # dimmed orange
    "teal":        "#00e5cc",   # secondary accent — electric teal
    "teal_dim":    "#006655",   # dimmed teal
    "amber":       "#ffb627",   # warning amber
    "red":         "#ff2d55",   # danger red
    "green":       "#39ff14",   # success neon green
    "text":        "#c8d8e8",   # primary text
    "text2":       "#6a8aaa",   # secondary text
    "text3":       "#2d4a6a",   # muted text
    "scanline":    "#ffffff",   # scanline overlay (very low alpha)
}

# Per-type colours
TYPE_C = {
    "mp4": "#00e5cc", "avi": "#00b8a9", "mkv": "#007f6e",
    "mov": "#4ecdc4", "flv": "#1a535c",
    "jpg": "#ff6b1a", "png": "#ffb627", "gif": "#ff9f1c",
    "pdf": "#ff2d55", "zip": "#a855f7",
}


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def _lerp(c1, c2, t):
    r1,g1,b1 = _hex_to_rgb(c1);  r2,g2,b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)


# ═══════════════════════════════════════════════════════════════════════════════
#  FONTS  — Orbitron-style via Tk font tricks; fallback to fixed/console
#  We try to pull Orbitron from the system; if unavailable we use a tight
#  monospace that still looks engineered.
# ═══════════════════════════════════════════════════════════════════════════════
def _best_font(*candidates):
    """Return the first font family available on this system."""
    import tkinter.font as tkf
    available = set(tkf.families())
    for c in candidates:
        if c in available:
            return c
    return "Courier"   # ultimate fallback

_DISPLAY = None   # resolved at startup
_MONO    = None


def _resolve_fonts(root):
    global _DISPLAY, _MONO
    _DISPLAY = _best_font("Orbitron", "Rajdhani", "Exo 2", "Oxanium",
                           "Share Tech Mono", "VT323", "Courier New")
    _MONO    = _best_font("JetBrains Mono", "Fira Code", "Cascadia Code",
                           "Consolas", "Lucida Console", "Courier New")


def F(family, size, *styles):
    return (family, size) + styles


# ═══════════════════════════════════════════════════════════════════════════════
#  ANIMATED CANVAS COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class RadarSweep(tk.Canvas):
    """
    Circular radar sweep — the hero widget.
    Shows: outer grid rings, sweep arm, ping blips, progress arc.
    """
    def __init__(self, parent, size=200):
        super().__init__(parent, width=size, height=size,
                         bg=P["void"], highlightthickness=0)
        self.size      = size
        self.cx = self.cy = size / 2
        self.r         = size / 2 - 10
        self._angle    = 0
        self._pct      = 0
        self._running  = False
        self._blips    = []
        self._after_id = None
        self.after(100, self._draw)

    def start(self):
        self._running = True
        self._loop()

    def stop(self):
        self._running = False

    def set_pct(self, pct):
        self._pct = min(float(pct), 100)
        if not self._running:
            self._draw()

    def _add_blip(self):
        if random.random() < 0.25:
            angle  = self._angle
            ring_r = random.uniform(self.r * 0.3, self.r * 0.9)
            self._blips.append([angle, ring_r, 0, random.randint(25, 55)])

    def _loop(self):
        if not self._running:
            return
        self._angle = (self._angle + 2) % 360
        self._add_blip()
        # Age blips
        self._blips = [[a, r, age+1, mx]
                       for a, r, age, mx in self._blips if age < mx]
        self._draw()
        self._after_id = self.after(20, self._loop)

    def _draw(self):
        self.delete("all")
        cx, cy, r = self.cx, self.cy, self.r

        # ── Background void circle
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         fill=P["void"], outline=P["rim"], width=1)

        # ── Concentric rings (4)
        for i in range(1, 5):
            rr = r * i / 4
            self.create_oval(cx-rr, cy-rr, cx+rr, cy+rr,
                              outline=P["rim"], width=1)

        # ── Cross-hairs
        self.create_line(cx-r, cy, cx+r, cy, fill=P["rim"], width=1)
        self.create_line(cx, cy-r, cx, cy+r, fill=P["rim"], width=1)

        # ── Progress arc (orange)
        if self._pct > 0:
            self.create_arc(cx-r+4, cy-r+4, cx+r-4, cy+r-4,
                            start=90, extent=-self._pct*3.6,
                            outline=P["orange"], width=2, style="arc")

        # ── Sweep trail (teal gradient)
        if self._running:
            for i in range(30):
                trail_angle = self._angle - i * 3
                alpha       = (1 - i/30) * 0.7
                col = _lerp(P["teal"], P["void"], 1 - alpha)
                self.create_arc(cx-r+8, cy-r+8, cx+r-8, cy+r-8,
                                start=90 - trail_angle, extent=-3,
                                outline=col, width=2, style="arc")

            # Sweep arm line
            arm_rad = math.radians(self._angle)
            ex = cx + r * math.cos(arm_rad)
            ey = cy - r * math.sin(arm_rad)
            self.create_line(cx, cy, ex, ey, fill=P["teal"], width=1)

            # Sweep tip glow
            self.create_oval(ex-3, ey-3, ex+3, ey+3,
                             fill=P["teal"], outline="")

        # ── Blips
        for angle, ring_r, age, max_age in self._blips:
            fade  = 1 - age / max_age
            rad   = math.radians(angle)
            bx    = cx + ring_r * math.cos(rad)
            by    = cy - ring_r * math.sin(rad)
            col   = _lerp(P["orange"], P["void"], 1 - fade)
            size  = max(1, int(4 * fade))
            self.create_oval(bx-size, by-size, bx+size, by+size,
                             fill=col, outline="")

        # ── Centre percentage
        pct_str = f"{self._pct:.0f}"
        self.create_text(cx, cy - 8,
                         text=pct_str,
                         font=(_DISPLAY or "Courier New", 22, "bold"),
                         fill=P["orange"])
        self.create_text(cx, cy + 14,
                         text="%",
                         font=(_DISPLAY or "Courier New", 10),
                         fill=P["text2"])


class GlowBar(tk.Canvas):
    """Thin animated progress bar with moving glow pulse."""
    def __init__(self, parent, h=5):
        super().__init__(parent, height=h, bg=P["surface"],
                         highlightthickness=0)
        self._pct    = 0
        self._pulse  = 0
        self._pdir   = 1
        self._active = False
        self.after(100, self._tick)

    def set_pct(self, pct):
        self._pct = min(float(pct), 100)
        self._render()

    def start(self):
        self._active = True

    def stop(self):
        self._active = False
        self._render()

    def _tick(self):
        if self._active:
            self._pulse += 0.04 * self._pdir
            if self._pulse >= 1: self._pdir = -1
            if self._pulse <= 0: self._pdir =  1
            self._render()
        self.after(25, self._tick)

    def _render(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2: return
        # Track
        self.create_rectangle(0, 0, w, h, fill=P["rim"], outline="")
        # Fill
        fw = int(w * self._pct / 100)
        if fw > 0:
            self.create_rectangle(0, 0, fw, h, fill=P["orange"], outline="")
            # Glow head
            gw  = min(60, fw)
            tip = _lerp(P["orange"], "#ffffff", 0.4 * self._pulse)
            self.create_rectangle(fw-gw, 0, fw, h, fill=tip, outline="")


class MatrixRain(tk.Canvas):
    """Subtle falling-character column effect for decorative panels."""
    def __init__(self, parent, rain_w=160, rain_h=80, cols=20):
        super().__init__(parent,
                         width=rain_w, height=rain_h,
                         bg=P["void"], highlightthickness=0)
        self._w     = rain_w
        self._h     = rain_h
        self._cols  = cols
        self._drops = [random.randint(-rain_h, 0) for _ in range(cols)]
        self._chars = "01ABCDEF"
        self.after(150, self._tick)

    def _tick(self):
        self.delete("all")
        col_w  = self._w / self._cols
        char_h = 12
        for i, y in enumerate(self._drops):
            x   = i * col_w + col_w / 2
            # Draw a small column of chars
            for j in range(6):
                yy    = y - j * char_h
                if 0 < yy < self._h:
                    alpha = 1 - j / 6
                    col   = _lerp(P["teal"], P["void"], 1 - alpha * 0.6)
                    c     = random.choice(self._chars)
                    self.create_text(x, yy, text=c,
                                     font=(_MONO or "Courier New", 8),
                                     fill=col)
            self._drops[i] = (y + char_h) % (self._h + 60)
        self.after(120, self._tick)


class ScanlineOverlay(tk.Canvas):
    """Subtle CRT scanline texture overlay."""
    def __init__(self, parent):
        super().__init__(parent, bg="", highlightthickness=0)
        self.bind("<Configure>", self._draw)

    def _draw(self, _=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        for y in range(0, h, 4):
            self.create_line(0, y, w, y, fill="#ffffff", stipple="gray12")


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLED WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class GlassFrame(tk.Frame):
    """A panel with an orange top-accent line — glassmorphism feel."""
    def __init__(self, parent, accent=None, **kw):
        kw.setdefault("bg", P["glass"])
        super().__init__(parent, **kw)
        accent = accent or P["orange"]
        tk.Frame(self, bg=accent, height=2).pack(fill="x", side="top")


class Tooltip:
    def __init__(self, widget, text):
        widget.bind("<Enter>", lambda e: self._show(e, text, widget))
        widget.bind("<Leave>", self._hide)
        self.tw = None

    def _show(self, _, text, widget):
        x = widget.winfo_rootx() + 24
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        self.tw = tk.Toplevel(widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=text,
                 bg=P["glass2"], fg=P["text2"],
                 font=(_MONO, 8),
                 padx=10, pady=5).pack()

    def _hide(self, _=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


def _accent_button(parent, text, cmd, accent=None, width=None):
    """A flat button with hover glow."""
    accent = accent or P["orange"]
    btn = tk.Label(parent, text=text,
                   bg=accent, fg=P["void"],
                   font=(_DISPLAY or "Courier New", 9, "bold"),
                   cursor="hand2", padx=16, pady=8,
                   width=width or 0)
    btn.bind("<Button-1>", lambda e: cmd())
    btn.bind("<Enter>",  lambda e: btn.config(bg=_lerp(accent, "#ffffff", 0.2)))
    btn.bind("<Leave>",  lambda e: btn.config(bg=accent))
    return btn


def _ghost_button(parent, text, cmd):
    """Outlined ghost button."""
    f = tk.Frame(parent, bg=P["rim"], padx=1, pady=1)
    lbl = tk.Label(f, text=text,
                   bg=P["glass"], fg=P["text2"],
                   font=(_MONO or "Courier New", 8, "bold"),
                   cursor="hand2", padx=12, pady=6)
    lbl.pack()
    f.bind("<Button-1>", lambda e: cmd())
    lbl.bind("<Button-1>", lambda e: cmd())
    lbl.bind("<Enter>", lambda e: lbl.config(fg=P["teal"], bg=P["glass2"]))
    lbl.bind("<Leave>", lambda e: lbl.config(fg=P["text2"], bg=P["glass"]))
    return f


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ByteRescueGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ByteRescue  ·  Forensic Recovery System")
        self.root.geometry("1360x900")
        self.root.minsize(1200, 800)
        self.root.configure(bg=P["void"])

        # ── State
        self.processed_state = {"bytes": 0}
        self.recovery_state  = {"files": [], "counts": {}, "saved_offsets": set()}
        self.lock            = threading.Lock()
        self.total_size      = 0
        self.scan_running    = False
        self.scan_start_time = None
        self._abort_flag     = False

        _resolve_fonts(root)
        self._build_ttk_styles()
        self._build_ui()
        self._load_drives()
        self._tick_clock()

    # ──────────────────────────────────────────────────────────────────────────
    #  TTK STYLES
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ttk_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        for name, bg in [("Dark.TCombobox", P["glass2"]),
                         ("Log.TScrollbar",  P["surface"])]:
            s.configure(name,
                        fieldbackground=bg,
                        background=bg,
                        foreground=P["text"],
                        arrowcolor=P["orange"],
                        bordercolor=P["rim"],
                        lightcolor=P["rim"],
                        darkcolor=P["rim"],
                        selectbackground=P["orange"],
                        selectforeground=P["void"])
            s.map(name, fieldbackground=[("readonly", bg)],
                  foreground=[("readonly", P["text"])])

        s.configure("Forensic.Treeview",
                    background=P["glass"],
                    foreground=P["text"],
                    fieldbackground=P["glass"],
                    borderwidth=0,
                    font=(_MONO or "Courier New", 9),
                    rowheight=26)
        s.configure("Forensic.Treeview.Heading",
                    background=P["glass2"],
                    foreground=P["orange"],
                    relief="flat",
                    font=(_DISPLAY or "Courier New", 8, "bold"))
        s.map("Forensic.Treeview",
              background=[("selected", P["rim_hi"])],
              foreground=[("selected", P["teal"])])

        s.configure("Vertical.TScrollbar",
                    background=P["glass2"],
                    troughcolor=P["surface"],
                    arrowcolor=P["text3"])
        s.configure("Horizontal.TScrollbar",
                    background=P["glass2"],
                    troughcolor=P["surface"],
                    arrowcolor=P["text3"])

    # ──────────────────────────────────────────────────────────────────────────
    #  BUILD UI
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.columnconfigure(0, weight=0, minsize=300)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    # ══════════════════════════════════════════════════════════════════════════
    #  LEFT PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_left_panel(self):
        left = tk.Frame(self.root, bg=P["surface"], width=300)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)

        # ── Orange left edge stripe
        tk.Frame(self.root, bg=P["orange"], width=3).place(x=0, y=0,
                                                            relheight=1)

        # ── Logo block
        logo = tk.Frame(left, bg=P["void"], pady=0)
        logo.grid(row=0, column=0, sticky="ew")
        tk.Frame(logo, bg=P["orange"], height=3).pack(fill="x")

        title_frame = tk.Frame(logo, bg=P["void"])
        title_frame.pack(fill="x", padx=20, pady=(18, 4))

        tk.Label(title_frame,
                 text="BYTE",
                 font=(_DISPLAY or "Courier New", 32, "bold"),
                 bg=P["void"], fg=P["orange"],
                 anchor="w").pack(fill="x")

        tk.Label(title_frame,
                 text="RESCUE",
                 font=(_DISPLAY or "Courier New", 32, "bold"),
                 bg=P["void"], fg=P["text"],
                 anchor="w").pack(fill="x")

        sub_row = tk.Frame(title_frame, bg=P["void"])
        sub_row.pack(fill="x", pady=(4, 0))
        tk.Frame(sub_row, bg=P["teal"], width=30, height=2).pack(side="left")
        tk.Label(sub_row,
                 text=f"  FORENSIC RECOVERY  v{TOOL_VERSION}",
                 font=(_MONO or "Courier New", 8),
                 bg=P["void"], fg=P["text3"]).pack(side="left")

        tk.Frame(logo, bg=P["rim"], height=1).pack(fill="x")

        # ── Decorative accent bar (replaces MatrixRain for stability)
        rain_frame = tk.Frame(left, bg=P["void"], height=40)
        rain_frame.grid(row=1, column=0, sticky="ew")
        rain_frame.grid_propagate(False)
        # Teal + orange alternating dots decoration
        dot_canvas = tk.Canvas(rain_frame, width=300, height=40,
                               bg=P["void"], highlightthickness=0)
        dot_canvas.pack()
        for i in range(0, 300, 12):
            col = P["teal"] if (i // 12) % 2 == 0 else P["orange_dim"]
            dot_canvas.create_rectangle(i, 18, i+8, 22, fill=col, outline="")

        # ── Radar
        radar_frame = tk.Frame(left, bg=P["surface"])
        radar_frame.grid(row=2, column=0, pady=10)
        self.radar = RadarSweep(radar_frame, size=200)
        self.radar.pack()

        # Radar label
        self.radar_label = tk.Label(left,
                                     text="[ SYSTEM IDLE ]",
                                     font=(_DISPLAY or "Courier New", 9),
                                     bg=P["surface"], fg=P["text3"])
        self.radar_label.grid(row=3, column=0, pady=(0, 8))

        tk.Frame(left, bg=P["rim"], height=1).grid(row=4, column=0, sticky="ew")

        # ── Controls
        ctrl = tk.Frame(left, bg=P["surface"])
        ctrl.grid(row=5, column=0, sticky="ew", padx=18, pady=14)
        ctrl.columnconfigure(0, weight=1)

        # Drive label
        tk.Label(ctrl, text="SELECT TARGET DRIVE",
                 font=(_DISPLAY or "Courier New", 8, "bold"),
                 bg=P["surface"], fg=P["text3"],
                 anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 5))

        drive_row = tk.Frame(ctrl, bg=P["surface"])
        drive_row.grid(row=1, column=0, sticky="ew")
        drive_row.columnconfigure(0, weight=1)

        self.drive_var = tk.StringVar()
        self.drive_box = ttk.Combobox(drive_row,
                                       textvariable=self.drive_var,
                                       style="Dark.TCombobox",
                                       state="readonly",
                                       font=(_MONO, 11))
        self.drive_box.grid(row=0, column=0, sticky="ew")

        refresh = tk.Label(drive_row, text=" ⟳ ",
                            font=(_MONO, 13), bg=P["surface"],
                            fg=P["teal"], cursor="hand2")
        refresh.grid(row=0, column=1, padx=(6, 0))
        refresh.bind("<Button-1>", lambda e: self._load_drives())
        Tooltip(refresh, "Refresh drive list")

        # Scan button
        self.scan_btn = _accent_button(ctrl, "▶  INITIATE SCAN",
                                        self._start_scan,
                                        accent=P["orange"])
        self.scan_btn.grid(row=2, column=0, sticky="ew",
                            pady=(12, 4), columnspan=2)

        self.stop_btn = _accent_button(ctrl, "■  ABORT",
                                        self._abort_scan,
                                        accent=P["red"])
        self.stop_btn.grid(row=3, column=0, sticky="ew",
                            columnspan=2, pady=(0, 0))
        self.stop_btn.config(bg=P["rim"], fg=P["text3"],
                              cursor="arrow")

        tk.Frame(left, bg=P["rim"], height=1).grid(row=6, column=0,
                                                    sticky="ew", pady=(12, 0))

        # ── Telemetry block
        tel = tk.Frame(left, bg=P["surface"])
        tel.grid(row=7, column=0, sticky="ew", padx=18, pady=12)
        tel.columnconfigure(1, weight=1)

        tk.Label(tel, text="TELEMETRY",
                 font=(_DISPLAY or "Courier New", 8, "bold"),
                 bg=P["surface"], fg=P["text3"]
                 ).grid(row=0, column=0, columnspan=2,
                         sticky="w", pady=(0, 8))

        self._tel_vars = {}
        rows = [
            ("STATUS",     "sv_status",    P["orange"]),
            ("ELAPSED",    "sv_elapsed",   P["text"]),
            ("DRIVE",      "sv_drive",     P["text"]),
            ("SCANNED",    "sv_scanned",   P["teal"]),
            ("RECOVERED",  "sv_recovered", P["green"]),
            ("THREADS",    "sv_threads",   P["text"]),
        ]
        for i, (lbl, attr, col) in enumerate(rows, start=1):
            tk.Label(tel, text=lbl,
                     font=(_MONO or "Courier New", 8),
                     bg=P["surface"], fg=P["text3"]
                     ).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value="—")
            self._tel_vars[attr] = var
            setattr(self, attr, var)
            tk.Label(tel, textvariable=var,
                     font=(_MONO or "Courier New", 8, "bold"),
                     bg=P["surface"], fg=col
                     ).grid(row=i, column=1, sticky="e", pady=2)

        self.sv_threads.set(str(DEFAULT_THREAD_COUNT))
        self.sv_status.set("IDLE")

        # ── Clock
        tk.Frame(left, bg=P["rim"], height=1).grid(row=8, column=0, sticky="ew")
        self.clock_var = tk.StringVar(value="00:00:00")
        tk.Label(left, textvariable=self.clock_var,
                 font=(_DISPLAY or "Courier New", 11),
                 bg=P["surface"], fg=P["text3"]
                 ).grid(row=9, column=0, pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    #  RIGHT PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_right_panel(self):
        right = tk.Frame(self.root, bg=P["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        self._build_header_bar(right)
        self._build_stat_row(right)
        self._build_workspace(right)

    def _build_header_bar(self, parent):
        bar = tk.Frame(parent, bg=P["void"], height=56)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        tk.Frame(bar, bg=P["teal"], height=2).pack(fill="x", side="top")

        inner = tk.Frame(bar, bg=P["void"])
        inner.pack(fill="both", expand=True, padx=16)

        # Left — title
        tk.Label(inner,
                 text="RECOVERY CONSOLE",
                 font=(_DISPLAY or "Courier New", 11, "bold"),
                 bg=P["void"], fg=P["text2"]
                 ).pack(side="left", pady=16)

        # Right actions
        self.status_badge = tk.Label(inner,
                                      text="◉  STANDBY",
                                      font=(_MONO or "Courier New", 8, "bold"),
                                      bg=P["glass"], fg=P["text3"],
                                      padx=10, pady=5)
        self.status_badge.pack(side="right", pady=14, padx=(6, 0))

        folder_btn = _ghost_button(inner, "📁 OUTPUT",
                                    self._open_output_folder)
        folder_btn.pack(side="right", pady=14, padx=(0, 6))

        # Filter
        tk.Label(inner, text="FILTER:",
                 font=(_MONO, 8), bg=P["void"],
                 fg=P["text3"]).pack(side="right", pady=14, padx=(0, 4))
        self.filter_var = tk.StringVar()
        self.filter_box = ttk.Combobox(inner,
                                        textvariable=self.filter_var,
                                        values=["ALL"] + get_supported_filetypes(),
                                        style="Dark.TCombobox",
                                        state="readonly",
                                        font=(_MONO, 8), width=7)
        self.filter_box.current(0)
        self.filter_box.pack(side="right", pady=14, padx=(0, 8))
        self.filter_box.bind("<<ComboboxSelected>>", self._update_file_list)

    def _build_stat_row(self, parent):
        row = tk.Frame(parent, bg=P["bg"])
        row.grid(row=1, column=0, sticky="ew", padx=10, pady=(8, 0))
        row.columnconfigure(tuple(range(7)), weight=1)

        # Progress bar row
        pb_wrap = tk.Frame(row, bg=P["glass"])
        pb_wrap.grid(row=0, column=0, columnspan=7, sticky="ew",
                     padx=2, pady=(0, 8))
        pb_wrap.columnconfigure(0, weight=1)

        pb_inner = tk.Frame(pb_wrap, bg=P["glass"], padx=14, pady=8)
        pb_inner.pack(fill="x")
        pb_inner.columnconfigure(0, weight=1)

        hdr = tk.Frame(pb_inner, bg=P["glass"])
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="SCAN PROGRESS",
                 font=(_DISPLAY or "Courier New", 8, "bold"),
                 bg=P["glass"], fg=P["text3"]
                 ).pack(side="left")
        self.pct_label = tk.Label(hdr,
                                   text="0.0 %",
                                   font=(_DISPLAY or "Courier New", 10, "bold"),
                                   bg=P["glass"], fg=P["orange"])
        self.pct_label.pack(side="right")

        self.glow_bar = GlowBar(pb_inner, h=6)
        self.glow_bar.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        # Stat cards
        card_defs = [
            ("TOTAL",     "cv_total",    P["orange"], "📦"),
            ("VIDEO",     "cv_videos",   P["teal"],   "🎬"),
            ("IMAGE",     "cv_images",   "#ffb627",   "🖼"),
            ("DOCUMENT",  "cv_docs",     P["red"],    "📄"),
            ("ARCHIVE",   "cv_arcs",     "#a855f7",   "🗜"),
            ("PARTIAL",   "cv_partial",  P["amber"],  "⚠"),
            ("THREADS",   "cv_threads",  P["green"],  "⚙"),
        ]
        for i, (label, attr, color, icon) in enumerate(card_defs):
            card = tk.Frame(row, bg=P["glass"],
                            highlightbackground=P["rim"],
                            highlightthickness=1)
            card.grid(row=1, column=i, sticky="ew", padx=3, pady=2)
            tk.Frame(card, bg=color, height=2).pack(fill="x")

            var = tk.StringVar(value="0")
            setattr(self, attr, var)

            tk.Label(card, text=icon,
                     font=("Segoe UI Emoji", 12),
                     bg=P["glass"], fg=color).pack(pady=(6, 0))
            tk.Label(card, textvariable=var,
                     font=(_DISPLAY or "Courier New", 16, "bold"),
                     bg=P["glass"], fg=color).pack(pady=(2, 0))
            tk.Label(card, text=label,
                     font=(_MONO or "Courier New", 7),
                     bg=P["glass"], fg=P["text3"]).pack(pady=(0, 6))

        self.cv_threads.set(str(DEFAULT_THREAD_COUNT))

    def _build_workspace(self, parent):
        pane = tk.PanedWindow(parent, orient="vertical",
                               bg=P["bg"], sashwidth=8,
                               sashrelief="flat")
        pane.grid(row=2, column=0, sticky="nsew",
                  padx=10, pady=(6, 10))

        # ── FILE TABLE
        ftable = GlassFrame(pane, accent=P["orange"])
        pane.add(ftable, minsize=220)

        # Header - pack
        fhdr = tk.Frame(ftable, bg=P["glass2"])
        fhdr.pack(fill="x", side="top")
        tk.Label(fhdr, text="  RECOVERED FILES",
                 font=(_DISPLAY or "Courier New", 8, "bold"),
                 bg=P["glass2"], fg=P["orange"],
                 pady=8).pack(side="left")
        self.file_count_lbl = tk.Label(fhdr, text="[ 0 ]",
                                        font=(_MONO, 8),
                                        bg=P["glass2"], fg=P["teal"])
        self.file_count_lbl.pack(side="left", padx=4)
        exp_btn = _ghost_button(fhdr, "⬆ EXPORT LIST",
                                 self._export_file_list)
        exp_btn.pack(side="right", pady=4, padx=8)

        # Tree container - pack
        tree_frame = tk.Frame(ftable, bg=P["glass"])
        tree_frame.pack(fill="both", expand=True)

        cols = ("name", "type", "size", "offset", "path")
        self.tree = ttk.Treeview(tree_frame, columns=cols,
                                  show="headings",
                                  selectmode="browse",
                                  style="Forensic.Treeview")
        self.tree.heading("name",   text="FILENAME")
        self.tree.heading("type",   text="TYPE")
        self.tree.heading("size",   text="SIZE")
        self.tree.heading("offset", text="DISK OFFSET")
        self.tree.heading("path",   text="PATH")
        self.tree.column("name",   width=280, anchor="w")
        self.tree.column("type",   width=60,  anchor="center")
        self.tree.column("size",   width=80,  anchor="e")
        self.tree.column("offset", width=110, anchor="center")
        self.tree.column("path",   width=400, anchor="w")

        tsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tree.yview)
        self.tree.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tsb.set)

        self.tree.bind("<Double-Button-1>", self._open_file)
        self.tree.bind("<Button-3>", self._context_menu)

        # ── LOG TERMINAL
        log_wrap = GlassFrame(pane, accent=P["teal"])
        pane.add(log_wrap, minsize=140)

        # Log header - pack
        log_hdr = tk.Frame(log_wrap, bg=P["glass2"])
        log_hdr.pack(fill="x", side="top")
        tk.Label(log_hdr, text="  SYS://LOG",
                 font=(_DISPLAY or "Courier New", 8, "bold"),
                 bg=P["glass2"], fg=P["teal"],
                 pady=8).pack(side="left")
        self.log_blink = tk.Label(log_hdr, text="●",
                                   font=(_MONO, 10),
                                   bg=P["glass2"], fg=P["text3"])
        self.log_blink.pack(side="left", padx=4)
        clr = _ghost_button(log_hdr, "CLEAR", self._clear_log)
        clr.pack(side="right", pady=4, padx=8)

        # Log text area - pack
        log_container = tk.Frame(log_wrap, bg=P["void"])
        log_container.pack(fill="both", expand=True)

        self.log_box = tk.Text(log_container,
                                bg=P["void"],
                                fg=P["teal"],
                                font=(_MONO or "Courier New", 9),
                                state="disabled",
                                wrap="none",
                                relief="flat", bd=0,
                                pady=10, padx=14,
                                insertbackground=P["teal"],
                                selectbackground=P["rim_hi"])
        lsb_y = ttk.Scrollbar(log_container, orient="vertical",
                               command=self.log_box.yview)
        lsb_x = ttk.Scrollbar(log_wrap, orient="horizontal",
                               command=self.log_box.xview)
        self.log_box.configure(yscrollcommand=lsb_y.set,
                                xscrollcommand=lsb_x.set)

        lsb_x.pack(side="bottom", fill="x")
        self.log_box.pack(side="left", fill="both", expand=True)
        lsb_y.pack(side="right", fill="y")

        # Log colour tags
        self.log_box.tag_configure("TS",      foreground=P["text3"])
        self.log_box.tag_configure("INFO",    foreground=P["text2"])
        self.log_box.tag_configure("FOUND",   foreground=P["teal"])
        self.log_box.tag_configure("SAVED",   foreground=P["green"])
        self.log_box.tag_configure("WARN",    foreground=P["amber"])
        self.log_box.tag_configure("ERROR",   foreground=P["red"])
        self.log_box.tag_configure("CRIT",    foreground=P["red"])
        self.log_box.tag_configure("DONE",    foreground=P["orange"])
        self.log_box.tag_configure("PARTIAL", foreground=P["amber"])

        self._log_blink_state = False
        self._blink_after     = None

    # ──────────────────────────────────────────────────────────────────────────
    #  DRIVES
    # ──────────────────────────────────────────────────────────────────────────
    def _load_drives(self):
        drives = get_available_drives()
        self.drive_box["values"] = drives
        if drives:
            self.drive_box.current(0)

    # ──────────────────────────────────────────────────────────────────────────
    #  CLOCK  +  LOG BLINK
    # ──────────────────────────────────────────────────────────────────────────
    def _tick_clock(self):
        self.clock_var.set(time.strftime("%H:%M:%S"))
        if self.scan_running and self.scan_start_time:
            el   = int(time.time() - self.scan_start_time)
            h, r = divmod(el, 3600)
            m, s = divmod(r, 60)
            self.sv_elapsed.set(f"{h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._tick_clock)

    def _start_log_blink(self):
        self._log_blink_state = not self._log_blink_state
        self.log_blink.config(
            fg=P["teal"] if self._log_blink_state else P["text3"])
        self._blink_after = self.root.after(600, self._start_log_blink)

    def _stop_log_blink(self):
        if self._blink_after:
            self.root.after_cancel(self._blink_after)
        self.log_blink.config(fg=P["text3"])

    # ──────────────────────────────────────────────────────────────────────────
    #  LOGGING
    # ──────────────────────────────────────────────────────────────────────────
    def append_log(self, message: str):
        msg = message.strip()
        tag = "INFO"
        if   "[FOUND]"    in msg: tag = "FOUND"
        elif "SAVED MP4"  in msg or "SAVED AVI" in msg: tag = "SAVED"
        elif "[SAVED]"    in msg: tag = "SAVED"
        elif "[PARTIAL]"  in msg: tag = "PARTIAL"
        elif "[WARN]"     in msg: tag = "WARN"
        elif "[ERROR]"    in msg or "[CRITICAL]" in msg: tag = "CRIT"
        elif "[DONE]"     in msg or "complete"   in msg.lower(): tag = "DONE"

        ts = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, f" {ts}  ", "TS")
        self.log_box.insert(tk.END, msg + "\n", tag)
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def _thread_log(self, msg):
        self.root.after(0, self.append_log, msg)

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    #  PROGRESS UPDATE LOOP
    # ──────────────────────────────────────────────────────────────────────────
    def _update_progress(self):
        if self.total_size == 0:
            return
        with self.lock:
            done = self.processed_state["bytes"]
        pct = min(done / self.total_size * 100, 100)

        self.radar.set_pct(pct)
        self.glow_bar.set_pct(pct)
        self.pct_label.config(text=f"{pct:.1f} %")

        mb_done  = done / (1024**2)
        mb_total = self.total_size / (1024**2)
        self.sv_scanned.set(f"{mb_done:.0f} / {mb_total:.0f} MB")

        counts  = self.recovery_state["counts"]
        total   = sum(counts.values())
        videos  = sum(counts.get(t, 0) for t in ("mp4","avi","mkv","mov","flv"))
        images  = sum(counts.get(t, 0) for t in ("jpg","png","gif"))
        docs    = counts.get("pdf", 0)
        arcs    = counts.get("zip", 0)

        self.cv_total.set(str(total))
        self.cv_videos.set(str(videos))
        self.cv_images.set(str(images))
        self.cv_docs.set(str(docs))
        self.cv_arcs.set(str(arcs))
        self.sv_recovered.set(str(total))
        self.file_count_lbl.config(text=f"[ {total} ]")

        # Radar label
        if self.scan_running:
            self.radar_label.config(
                text=f"[ SCANNING  {pct:.0f}% ]",
                fg=P["orange"])

        if self.scan_running:
            self.root.after(200, self._update_progress)

    # ──────────────────────────────────────────────────────────────────────────
    #  FILE LIST
    # ──────────────────────────────────────────────────────────────────────────
    def _update_file_list(self, _=None):
        self.tree.delete(*self.tree.get_children())
        sel = self.filter_var.get()

        with self.lock:
            snap = list(self.recovery_state["files"])

        for fpath in snap:
            p = Path(fpath)
            if not p.exists():
                continue
            ext = p.suffix.lstrip(".").lower()
            if sel != "ALL" and ext != sel.lower():
                continue

            sz   = p.stat().st_size
            s_str = (f"{sz/(1024**2):.1f} MB" if sz >= 1024**2
                     else f"{sz//1024} KB")

            # Try to extract offset from filename  e.g. ..._0x1A2B.mp4
            offset_str = "—"
            parts = p.stem.split("_")
            for part in reversed(parts):
                if part.startswith("0x") or part.startswith("0X"):
                    offset_str = part
                    break

            color_tag = ext if ext in TYPE_C else "default"
            self.tree.insert("", "end",
                             values=(p.name, ext.upper(), s_str,
                                     offset_str, str(p)),
                             tags=(color_tag,))

        for ext, col in TYPE_C.items():
            self.tree.tag_configure(ext, foreground=col)

    def _schedule_file_list_update(self):
        self.root.after(0, self._update_file_list)

    # ──────────────────────────────────────────────────────────────────────────
    #  FILE ACTIONS
    # ──────────────────────────────────────────────────────────────────────────
    def _selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][4]

    def _open_file(self, _=None):
        p = self._selected_path()
        if p and Path(p).exists():
            os.startfile(str(p))

    def _open_output_folder(self):
        f = Path.cwd() / OUTPUT_FOLDER_NAME
        if f.exists():
            os.startfile(str(f))

    def _export_file_list(self):
        out = Path.cwd() / OUTPUT_FOLDER_NAME / "file_list.txt"
        with self.lock:
            files = list(self.recovery_state["files"])
        with open(out, "w") as f:
            for fp in files:
                f.write(fp + "\n")
        messagebox.showinfo("Exported", f"File list saved to:\n{out}")

    def _context_menu(self, event):
        p = self._selected_path()
        if not p:
            return
        m = tk.Menu(self.root, tearoff=0,
                    bg=P["glass2"], fg=P["text"],
                    activebackground=P["rim_hi"],
                    activeforeground=P["teal"],
                    font=(_MONO, 8), bd=0)
        m.add_command(label="▶  Open File",
                      command=self._open_file)
        m.add_command(label="📁  Open Folder",
                      command=lambda: os.startfile(str(Path(p).parent)))
        m.add_separator()
        m.add_command(label="📋  Copy Path",
                      command=lambda: (self.root.clipboard_clear(),
                                       self.root.clipboard_append(p)))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ──────────────────────────────────────────────────────────────────────────
    #  SCAN CONTROL
    # ──────────────────────────────────────────────────────────────────────────
    def _set_scan_ui(self, scanning):
        if scanning:
            self.scan_btn.config(bg=P["rim"], fg=P["text3"], cursor="arrow")
            self.stop_btn.config(bg=P["red"], fg=P["void"], cursor="hand2")
            self.status_badge.config(text="◉  SCANNING",
                                      bg=P["orange"], fg=P["void"])
            self.sv_status.set("ACTIVE")
            self.radar_label.config(text="[ SCANNING ]", fg=P["orange"])
            self.radar.start()
            self.glow_bar.start()
            self._start_log_blink()
        else:
            self.scan_btn.config(bg=P["orange"], fg=P["void"],
                                  cursor="hand2")
            self.stop_btn.config(bg=P["rim"], fg=P["text3"],
                                  cursor="arrow")
            self.radar.stop()
            self.glow_bar.stop()
            self._stop_log_blink()

    def _start_scan(self):
        if self.scan_running:
            return
        letter = self.drive_var.get()
        if not validate_drive_letter(letter):
            messagebox.showerror("Error", "Invalid drive.")
            return

        # Reset
        self.scan_running    = True
        self._abort_flag     = False
        self.scan_start_time = time.time()
        self.processed_state = {"bytes": 0}
        self.recovery_state  = {"files": [], "counts": {}, "saved_offsets": set()}

        self.tree.delete(*self.tree.get_children())
        self._clear_log()
        for attr in ("cv_total","cv_videos","cv_images",
                     "cv_docs","cv_arcs","cv_partial"):
            getattr(self, attr).set("0")
        self.sv_elapsed.set("00:00:00")

        self._set_scan_ui(True)
        self.append_log(f"[INFO] ═══ ByteRescue v{TOOL_VERSION} ═══")
        self.append_log(f"[INFO] Target drive   : {letter}:")
        self.append_log(f"[INFO] Scan threads   : {DEFAULT_THREAD_COUNT}")

        threading.Thread(target=self._run_scan,
                          args=(letter,), daemon=True).start()
        self.root.after(200, self._update_progress)

    def _abort_scan(self):
        if not self.scan_running:
            return
        self._abort_flag = True
        self.scan_running = False
        self.append_log("[WARN] ─── Scan aborted by operator ───")
        self._finish_cleanup("ABORTED")

    def _run_scan(self, letter):
        try:
            total_size, mode = get_drive_size(letter)
            self.total_size  = total_size
            gb = total_size / 1024**3
            self.root.after(0, lambda: self.sv_drive.set(f"{gb:.1f} GB"))
            self.root.after(0, lambda: self.append_log(
                f"[INFO] Drive size     : {gb:.1f} GB  [{mode}]"))

            if mode != "RAW":
                self.root.after(0, lambda: messagebox.showerror(
                    "Access Denied",
                    "RAW access failed.\nRun ByteRescue as Administrator."))
                self.root.after(0, lambda: self._finish_cleanup("FAILED"))
                return

            drive_path = get_raw_drive_path(letter)
            signatures = get_signatures()
            types      = get_supported_filetypes()
            base       = Path.cwd() / OUTPUT_FOLDER_NAME
            folders    = create_output_structure(base, types)

            chunk      = total_size // DEFAULT_THREAD_COUNT
            threads    = []

            for i in range(DEFAULT_THREAD_COUNT):
                s = i * chunk
                e = total_size if i == DEFAULT_THREAD_COUNT - 1 \
                    else (i + 1) * chunk
                t = RecoveryThread(
                    name=f"T{i+1}",
                    start_offset=s, end_offset=e,
                    drive_path=drive_path,
                    signatures=signatures,
                    output_folders=folders,
                    total_size=total_size,
                    processed_state=self.processed_state,
                    lock=self.lock,
                    recovery_state=self.recovery_state,
                    log_callback=self._thread_log,
                    file_found_callback=self._schedule_file_list_update,
                )
                threads.append(t)

            for t in threads: t.start()
            for t in threads: t.join()

            self.root.after(0, self._finish_scan, folders)

        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            self.root.after(0, lambda: self._finish_cleanup("FAILED"))

    # ──────────────────────────────────────────────────────────────────────────
    #  FINISH
    # ──────────────────────────────────────────────────────────────────────────
    def _finish_cleanup(self, status="COMPLETE"):
        self.scan_running = False
        self._set_scan_ui(False)

        colors = {"COMPLETE": P["green"], "ABORTED": P["amber"],
                  "FAILED":   P["red"]}
        col = colors.get(status, P["text2"])
        self.status_badge.config(text=f"◉  {status}",
                                  bg=P["glass2"], fg=col)
        self.sv_status.set(status)
        self.radar_label.config(text=f"[ {status} ]", fg=col)
        self.radar.set_pct(100 if status == "COMPLETE" else self.radar._pct)

    def _finish_scan(self, folders):
        self._finish_cleanup("COMPLETE")
        self._update_file_list()

        total = len(self.recovery_state["files"])
        self.append_log("─" * 54)
        self.append_log(f"[DONE] Scan complete — {total} files recovered.")
        self.append_log(f"[INFO] Output : {folders['reports'].parent}")

        report_data = {
            "timestamp":       get_timestamp(),
            "tool_name":       TOOL_NAME,
            "total_recovered": total,
            "file_counts":     self.recovery_state["counts"],
            "recovered_files": self.recovery_state["files"],
        }
        generate_text_report(report_data, folders["reports"])
        generate_json_report(report_data, folders["reports"])

        messagebox.showinfo(
            "Scan Complete",
            f"Recovery finished successfully.\n\n"
            f"Files recovered  :  {total}\n"
            f"Output folder    :  {folders['reports'].parent}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app  = ByteRescueGUI(root)
    root.mainloop()

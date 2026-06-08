#!/usr/bin/env python3
"""
Sigma Harmonics Step 2 - Glyph Replacement Patch
=================================================
Replaces glyphs 88..93 in the NFTR dialog font (ID05585.bin)
with pre-rotated ASCII characters for "dream?" readable in book mode.

The game's script outputs glyphs 88..93 for the text "...夢？".
By replacing those 6 glyph bitmaps with our English characters,
the text will display as "dream?" in book mode without any bytecode changes.

Glyph format:
  - File: extracted_cpk/ID05585.bin (RTFN/NFTR format)
  - Cell: 9×9 pixels, 9 bytes per glyph (1 byte per row, 8 visible columns)
  - Glyph data starts at file offset 0x50
  - Glyph 88: offset 0x50 + 88*9 = 0x50 + 792 = 0x368
  - Glyphs 88..93: the "...夢？" characters

Rotation:
  - DS held normally: glyph renders upright, text flows top→bottom
  - DS in book mode (rotated 90° CCW): glyphs appear sideways
  - Pre-rotate 90° CW so they appear upright in book mode
"""

import struct
import shutil
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
CPK_DIR   = Path("extracted_cpk")
OUT_DIR   = Path("modified_cpk")
FONT_FILE = "ID05585.bin"

OUT_DIR.mkdir(exist_ok=True)

# ── Font constants ─────────────────────────────────────────────────────────────
GLYPH_START = 0x50
BPG         = 9       # bytes per glyph
FONT_GLYPHS = 95      # total existing glyphs

# Target glyphs to replace (the "...夢？" sequence)
TARGET_GLYPHS = [88, 89, 90, 91, 92, 93]  # 6 glyphs

# ── ASCII glyph bitmaps ────────────────────────────────────────────────────────
# 8 cols × 9 rows, 1bpp, MSB = leftmost pixel
# Designed to be legible at small size in book mode after 90° CW rotation

def make_glyph(*rows):
    """Create a 9-byte glyph from row bitmasks. Pad with zeros to 9 rows."""
    g = list(rows) + [0] * (9 - len(rows))
    return bytes(g[:9])

GLYPHS_RAW = {
    # "dream?" — 6 chars for 6 glyph slots (88..93)
    'd': make_glyph(0b00000100,   #  ·····█··
                    0b00000100,   #  ·····█··
                    0b00111100,   #  ··████··
                    0b01000100,   #  ·█···█··
                    0b01000100,   #  ·█···█··
                    0b01000100,   #  ·█···█··
                    0b00111100,   #  ··████··
                    ),
    'r': make_glyph(0b00000000,   #  ········
                    0b00000000,   #  ········
                    0b01011000,   #  ·█·██···
                    0b01100000,   #  ·██·····
                    0b01000000,   #  ·█······
                    0b01000000,   #  ·█······
                    0b01000000,   #  ·█······
                    ),
    'e': make_glyph(0b00000000,   #  ········
                    0b00000000,   #  ········
                    0b00111000,   #  ··███···
                    0b01001000,   #  ·█··█···
                    0b01111000,   #  ·████···
                    0b01000000,   #  ·█······
                    0b00111000,   #  ··███···
                    ),
    'a': make_glyph(0b00000000,   #  ········
                    0b00000000,   #  ········
                    0b00111000,   #  ··███···
                    0b00000100,   #  ·····█··
                    0b00111100,   #  ··████··
                    0b01000100,   #  ·█···█··
                    0b00111100,   #  ··████··
                    ),
    'm': make_glyph(0b00000000,   #  ········
                    0b00000000,   #  ········
                    0b01101000,   #  ·██·█···
                    0b01010100,   #  ·█·█·█··
                    0b01010100,   #  ·█·█·█··
                    0b01000100,   #  ·█···█··
                    0b01000100,   #  ·█···█··
                    ),
    '?': make_glyph(0b00111000,   #  ··███···
                    0b01001000,   #  ·█··█···
                    0b00001000,   #  ····█···
                    0b00010000,   #  ···█····
                    0b00100000,   #  ··█·····
                    0b00000000,   #  ········
                    0b00100000,   #  ··█·····
                    ),
}

REPLACEMENT_CHARS = ['d', 'r', 'e', 'a', 'm', '?']  # maps to glyphs 88..93


# ── Glyph rotation ────────────────────────────────────────────────────────────
def rotate_90cw(glyph_bytes, src_w=8, src_h=9):
    """
    Rotate 90° clockwise so the glyph appears upright in book mode.
    
    DS book mode = DS rotated 90° CCW from normal.
    If we pre-rotate 90° CW, the result after device rotation = upright.
    
    CW rotation: new_grid[col][src_h-1-row] = old_grid[row][col]
    Output: new_h=src_w=8, new_w=src_h=9 → stored as 9 bytes (8 visible cols)
    """
    # Read pixels
    src = [[0]*src_w for _ in range(src_h)]
    for r in range(src_h):
        for c in range(src_w):
            src[r][c] = (glyph_bytes[r] >> (7 - c)) & 1

    # CW: new[c][src_h-1-r] = old[r][c]
    new_h, new_w = src_w, src_h  # = 8, 9
    new = [[0]*new_w for _ in range(new_h)]
    for r in range(src_h):
        for c in range(src_w):
            new[c][src_h - 1 - r] = src[r][c]

    # Encode back: 9 bytes, 8 cols per row (drop 9th col to fit in 1 byte)
    result = bytearray(9)
    for row in range(new_h):  # rows 0..7
        byte = 0
        for col in range(8):  # only 8 of the 9 new columns fit
            if new[row][col]:
                byte |= (1 << (7 - col))
        result[row] = byte
    result[8] = 0  # pad row 8
    return bytes(result)


def show_glyph(glyph_bytes, label="", cols=8):
    if label:
        print(f"  {label}:")
    for b in glyph_bytes:
        print("    " + ''.join('█' if (b >> (7-c)) & 1 else '·' for c in range(cols)))


# ── Generate rotated glyphs ────────────────────────────────────────────────────
print("=" * 60)
print("Generating rotated ASCII glyphs for 'dream?'")
print("=" * 60)

rotated = {}
for char in REPLACEMENT_CHARS:
    raw = GLYPHS_RAW[char]
    rot = rotate_90cw(raw)
    rotated[char] = rot
    print(f"\n'{char}' (glyph {88 + REPLACEMENT_CHARS.index(char)}):")
    print("  Original (upright, DS normal):")
    show_glyph(raw)
    print("  Rotated 90° CW (upright in book mode):")
    show_glyph(rot)


# ── Patch the font ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Patching NFTR font")
print("=" * 60)

font_data = bytearray((CPK_DIR / FONT_FILE).read_bytes())
print(f"Font size: {len(font_data)} bytes")

for i, char in enumerate(REPLACEMENT_CHARS):
    glyph_idx = TARGET_GLYPHS[i]  # 88..93
    file_off   = GLYPH_START + glyph_idx * BPG

    old = bytes(font_data[file_off : file_off + BPG])
    new = rotated[char]

    print(f"\nGlyph {glyph_idx} ('{char}') at file+{file_off:x}:")
    print(f"  Old: {old.hex()}")
    print(f"  New: {new.hex()}")

    font_data[file_off : file_off + BPG] = new

out_path = OUT_DIR / FONT_FILE
out_path.write_bytes(font_data)
print(f"\n✅ Font saved → {out_path}")
print(f"   Modified glyphs 88..93 with 'd','r','e','a','m','?' (rotated 90° CW)")


# ── Verify the patch ───────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Verification - showing final glyph shapes")
print("=" * 60)

patched_font = out_path.read_bytes()
for i, char in enumerate(REPLACEMENT_CHARS):
    glyph_idx = TARGET_GLYPHS[i]
    file_off   = GLYPH_START + glyph_idx * BPG
    glyph      = patched_font[file_off : file_off + BPG]
    print(f"\nGlyph {glyph_idx} → '{char}' (book mode view, rotated 90° CW):")
    for b in glyph:
        print("  " + ''.join('█' if (b >> (7-c)) & 1 else '·' for c in range(8)))

print("\nDone! Next step: repack CPK and rebuild ROM.")
print("Use patch_textbox_position.py to rebuild the full ROM.")

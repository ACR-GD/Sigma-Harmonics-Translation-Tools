#!/usr/bin/env python3
"""
Sigma Harmonics Step 2 - Correct Glyph Replacement (v3)
=========================================================
CORRECTLY patches the Japanese dialog glyphs in ID05585.bin.

KEY FINDINGS (from analysis):
- ID05585.bin is a HYBRID NFTR+custom-script file
- Only the FIRST 21 glyph slots (0-20) contain actual character bitmaps
- Glyph indices in the script are SIGNED 16-bit, negative = relative from end
  (-6 = glyph 15, -5 = glyph 16, -4 = glyph 17, -3 = glyph 18, -2 = glyph 19)
- Glyph structure: [bx(1)] [char_width(1)] [row0..row8(9 bytes, 8px/row, 1bpp)]

FIRST DIALOG LINE "。。。夢？":
Script at ID04167.bin+0x011C: 05 FA FF 05 FB FF 05 FC FF 05 FD FF 05 FE FF
  Glyph 15 (0x00E1) = "。" → replace with 'd'
  Glyph 16 (0x00EC) = "。" → replace with 'r'
  Glyph 17 (0x00F7) = "。" → replace with 'e'
  Glyph 18 (0x0102) = "夢" → replace with 'a'
  Glyph 19 (0x010D) = "？" → replace with 'm'

ROTATION NOTE:
Glyphs are displayed in DS book mode (DS rotated 90° CCW). To appear upright,
bitmaps must be pre-rotated 90° CW.
"""

import struct
from pathlib import Path

# Paths
FONT_IN  = Path('extracted_cpk/ID05585.bin')
FONT_OUT = Path('modified_cpk/ID05585.bin')

# CORRECT constants (verified by analysis)
GLYPH_START  = 60      # offset of first glyph: NFTR header(16) + FINF(28) + CGLP header(16) = 60
GLYPH_LEN    = 11      # bytes per glyph: [bx(1)] [width(1)] [row0-row8(9)]
VALID_GLYPHS = 21      # only 21 actual glyph bitmaps exist in the font

# Target glyphs for first dialog line "。。。夢？"
# Script uses negative indices: -6=glyph15, -5=glyph16, -4=glyph17, -3=glyph18, -2=glyph19
TARGETS = [
    (15, 'A'),  # "。" (dot 1) → 'A'
    (16, ' '),  # "。" (dot 2) → space (or another char)
    (17, 'd'),  # "。" (dot 3) → 'd'
    (18, 'r'),  # "夢" (dream) → 'r'
    (19, 'm'),  # "？" (?) → 'm' 
]
# → Will display "A dr m" ... let me use a better 5-char phrase
# Since there are exactly 5 slots, use "dream" without "?"
TARGETS = [
    (15, 'd'),  # first char (leftmost in RTL = last drawn = "？" position)
    (16, 'r'),
    (17, 'e'),
    (18, 'a'),
    (19, 'm'),
]
# NOTE: Since text is RIGHT-TO-LEFT, glyph 19 (last) appears on LEFT, glyph 15 on RIGHT.
# So visually: m · a · e · r · d (right to left: dream)
# In book mode the characters read: d r e a m (reading direction matches)

# ── Glyph bitmaps (8×9, 1bpp, MSB=leftmost pixel) ──────────────────────────
def make_bitmap(*rows):
    """Create 9 row bytes from up to 9 integer bitmasks."""
    g = list(rows) + [0] * (9 - len(rows))
    return bytes(g[:9])

# Classic pixel font chars at 8×8, padded to 9 rows
GLYPHS = {
    'd': make_bitmap(
        0b00000100,   # ·····█··
        0b00000100,   # ·····█··
        0b00111100,   # ··████··
        0b01000100,   # ·█···█··
        0b01000100,   # ·█···█··
        0b01000100,   # ·█···█··
        0b00111100,   # ··████··
    ),
    'r': make_bitmap(
        0b00000000,
        0b00000000,
        0b01011000,   # ·█·██···
        0b01100000,   # ·██·····
        0b01000000,   # ·█······
        0b01000000,   # ·█······
        0b01000000,   # ·█······
    ),
    'e': make_bitmap(
        0b00000000,
        0b00000000,
        0b00111000,   # ··███···
        0b01001000,   # ·█··█···
        0b01111000,   # ·████···
        0b01000000,   # ·█······
        0b00111000,   # ··███···
    ),
    'a': make_bitmap(
        0b00000000,
        0b00000000,
        0b00111000,   # ··███···
        0b00000100,   # ·····█··
        0b00111100,   # ··████··
        0b01000100,   # ·█···█··
        0b00111100,   # ··████··
    ),
    'm': make_bitmap(
        0b00000000,
        0b00000000,
        0b01101000,   # ·██·█···
        0b01010100,   # ·█·█·█··
        0b01010100,   # ·█·█·█··
        0b01000100,   # ·█···█··
        0b01000100,   # ·█···█··
    ),
    '?': make_bitmap(
        0b00111000,   # ··███···
        0b01001000,   # ·█··█···
        0b00001000,   # ····█···
        0b00010000,   # ···█····
        0b00100000,   # ··█·····
        0b00000000,
        0b00100000,   # ··█·····
    ),
}


def rotate_90cw(bitmap_9bytes, src_w=8, src_h=9):
    """
    Rotate a glyph 90° clockwise so it appears upright in book mode.
    Input: 9 bytes (8 pixels per row, 9 rows)
    Output: 9 bytes (8 pixels per row, after rotation)
    CW rotation: new[c][src_h-1-r] = old[r][c]
    Result: new size is src_w × src_h = 8×9 (same dimensions, but rotated content)
    """
    src = [[0]*src_w for _ in range(src_h)]
    for r in range(src_h):
        for c in range(src_w):
            src[r][c] = (bitmap_9bytes[r] >> (7 - c)) & 1
    
    # After 90° CW: new grid is src_w rows × src_h cols
    new_h, new_w = src_w, src_h  # = 8, 9
    new = [[0]*new_w for _ in range(new_h)]
    for r in range(src_h):
        for c in range(src_w):
            new[c][src_h - 1 - r] = src[r][c]
    
    # Encode back to 9 bytes: take 8 of the 9 new columns (truncate last)
    result = bytearray(9)
    for row_i in range(new_h):  # 8 rows
        byte = 0
        for col_i in range(8):  # 8 of 9 columns
            if new[row_i][col_i]:
                byte |= (1 << (7 - col_i))
        result[row_i] = byte
    result[8] = 0  # 9th row = 0
    return bytes(result)


def show_glyph(bitmap_9bytes, label=""):
    if label:
        print(f"  {label}:")
    for b in bitmap_9bytes:
        print("    " + ''.join('█' if (b >> (7-c)) & 1 else '·' for c in range(8)))


# ── Main ─────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Sigma Harmonics Step 2 - Glyph Replacement (CORRECT)")
print("=" * 60)

data = bytearray(FONT_IN.read_bytes())
print(f"Font: {FONT_IN} ({len(data)} bytes)")

print(f"\nTarget: glyphs 15-19 at file offsets:")
for glyph_idx, char in TARGETS:
    off = GLYPH_START + glyph_idx * GLYPH_LEN
    print(f"  Glyph {glyph_idx} → '{char}' at offset {off} (0x{off:04x})")

print(f"\nReplacing glyphs...")
for glyph_idx, char in TARGETS:
    off = GLYPH_START + glyph_idx * GLYPH_LEN
    
    old_raw = bytes(data[off:off+GLYPH_LEN])
    
    raw_bitmap = GLYPHS[char]
    rotated    = rotate_90cw(raw_bitmap)
    
    # Build new glyph: [bx=0] [width=8] [9 bitmap rows]
    new_glyph = bytes([0, 8]) + rotated
    
    data[off:off+GLYPH_LEN] = new_glyph
    
    print(f"\n  Glyph {glyph_idx} '{char}' (offset 0x{off:04x}):")
    print(f"    OLD: {old_raw.hex()}")
    print(f"    NEW: {new_glyph.hex()}")
    print(f"    Rotated bitmap (90° CW — upright in book mode):")
    show_glyph(rotated)

# Save
FONT_OUT.parent.mkdir(exist_ok=True)
FONT_OUT.write_bytes(data)
print(f"\n✅ Font saved to {FONT_OUT}")

# Verify
print("\n=== Verification ===")
check = FONT_OUT.read_bytes()
for glyph_idx, char in TARGETS:
    off = GLYPH_START + glyph_idx * GLYPH_LEN
    g = check[off:off+GLYPH_LEN]
    print(f"Glyph {glyph_idx} '{char}': {g.hex()}")
    for b in g[2:]:
        print("  " + ''.join('█' if (b>>(7-c))&1 else '·' for c in range(8)))
    print()

print("Done! Now run build_step2_rom.py to inject into ROM.")

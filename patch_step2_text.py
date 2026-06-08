#!/usr/bin/env python3
"""
Sigma Harmonics - Step 2 Final Patch
=====================================
Patches the text "...夢？" → "A dream...?" in the game's dialog system.

Strategy:
  1. Add 9 new rotated ASCII glyphs to the NFTR font (ID05585.bin)
  2. Replace the 6-glyph sequence (glyphs 88-93 = "...夢？") in the script
     bytecode with 11-glyph sequence for "A dream...?" (A, space, d, r, e, a, m, ., ., ., ?)
  3. Repack both files into the CPK and rebuild the ROM

Script bytecode analysis:
  - At bc+0x50: opcode 07 (output sequence)
  - At bc+0x51-0x62: 6 chars (glyphs 88..93) = "...夢？"
  - Format: 05 XX YY = output char with glyph index
  - U+FFF9..FFFE = glyphs 88..93 (negative indices from end of font)

Font analysis:
  - ID05585.bin: RTFN (NFTR) format, 9×9 cells, 9 bytes per glyph
  - 95 existing glyphs (0..94)
  - Glyph data at file offset 0x50
  - New glyphs append at end of PLGC section (0x3ac)
"""

import struct
import shutil
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
CPK_DIR    = Path("extracted_cpk")
OUT_DIR    = Path("modified_cpk")
FONT_ID    = "ID05585"
SCRIPT_ID  = "ID04167"

FONT_IN    = CPK_DIR / f"{FONT_ID}.bin"
FONT_OUT   = OUT_DIR / f"{FONT_ID}.bin"
SCRIPT_IN  = CPK_DIR / f"{SCRIPT_ID}.bin"
SCRIPT_OUT = OUT_DIR / f"{SCRIPT_ID}.bin"

OUT_DIR.mkdir(exist_ok=True)

# ── Font constants ────────────────────────────────────────────────────────────
GLYPH_START    = 0x50   # file offset where glyph bitmaps start
BYTES_PER_GLYPH = 9     # 9 rows × 1 byte (8 visible columns per row)
N_ORIG_GLYPHS  = 95     # existing glyph count
PLGC_START     = 0x2c   # PLGC section offset
PLGC_SIZE_ORIG = 0x380  # original PLGC section size (bytes)
PLGC_END       = PLGC_START + PLGC_SIZE_ORIG  # = 0x3ac

# ── Script constants ──────────────────────────────────────────────────────────
BC_OFFSET      = 0x714   # bytecode section start in script file
# At bc+0x50: "07" = start output sequence
# At bc+0x51..0x62: 6 chars (each 3 bytes: 05 + u16 glyph code)
TEXT_OPCODE_OFF = 0x50   # offset within bytecode where "...夢？" sequence starts
# Full sequence: 07 [05 F9FF] [05 FAFF] [05 FBFF] [05 FCFF] [05 FDFF] [05 FEFF]
# = opcode(1) + 6×char(3) = 19 bytes total

# ── ASCII glyph bitmaps (8×9, 1bpp, upright in DS orientation) ───────────────
RAW_GLYPHS = {
    ' ': bytes([0,0,0,0,0,0,0,0,0]),
    'A': bytes([0b00111000, 0b01000100, 0b01000100, 0b01000100,
                0b01111100, 0b01000100, 0b01000100, 0, 0]),
    'd': bytes([0b00000100, 0b00000100, 0b00000100, 0b00111100,
                0b01000100, 0b01000100, 0b00111100, 0, 0]),
    'r': bytes([0, 0, 0b01011000, 0b01100000, 0b01000000, 0b01000000, 0b01000000, 0, 0]),
    'e': bytes([0, 0, 0b00111000, 0b01001000, 0b01111000, 0b01000000, 0b00111000, 0, 0]),
    'a': bytes([0, 0, 0b00111000, 0b00000100, 0b00111100, 0b01000100, 0b00111100, 0, 0]),
    'm': bytes([0, 0, 0b01101000, 0b01010100, 0b01010100, 0b01000100, 0b01000100, 0, 0]),
    '.': bytes([0, 0, 0, 0, 0, 0b01000000, 0b01000000, 0, 0]),
    '?': bytes([0b00111000, 0b01001000, 0b00001000, 0b00010000,
                0b00100000, 0, 0b00100000, 0, 0]),
}

NEEDED = ['A', ' ', 'd', 'r', 'e', 'a', 'm', '.', '?']


def rotate_90cw(glyph_bytes, src_w=8, src_h=9):
    """
    Rotate a glyph 90° clockwise.
    For a DS game held in book mode (rotated 90° CCW from normal),
    a character pre-rotated 90° CW will appear upright.
    
    Input:  src_w=8 cols, src_h=9 rows → 9 bytes (1 byte per row)
    Output: 8 rows × 9 cols → padded to 9 rows × 8 cols = 9 bytes
    
    90° CW formula: new[c][src_h-1-r] = old[r][c]
      → new_row = c (old column), new_col = src_h-1-r (flipped old row)
    """
    # Read source pixels into 2D grid
    src = [[0]*src_w for _ in range(src_h)]
    for r in range(src_h):
        for c in range(src_w):
            src[r][c] = (glyph_bytes[r] >> (7 - c)) & 1

    # new dimensions after CW rotation: new_h=src_w=8, new_w=src_h=9
    new_h, new_w = src_w, src_h  # = 8, 9
    new = [[0]*new_w for _ in range(new_h)]
    for r in range(src_h):
        for c in range(src_w):
            new[c][src_h - 1 - r] = src[r][c]

    # Encode: 9 bytes (pad to src_h=9 rows); each row uses 8 of 9 cols
    result = bytearray(9)
    for row in range(new_h):  # 8 rows
        byte = 0
        for col in range(min(new_w, 8)):  # only 8 cols per byte
            if new[row][col]:
                byte |= (1 << (7 - col))
        result[row] = byte
    result[8] = 0  # padding row
    return bytes(result)


def show_glyph(glyph_bytes, label="", cols=8):
    """Print glyph as ASCII art."""
    if label:
        print(f"  {label}:")
    for b in glyph_bytes:
        print("    " + ''.join('█' if (b >> (7-c)) & 1 else '·' for c in range(cols)))


# ── Step 1: Generate rotated glyphs ──────────────────────────────────────────
print("=" * 60)
print("STEP 1: Generating rotated ASCII glyphs")
print("=" * 60)

rotated_glyphs = {}
new_glyph_indices = {}
for i, char in enumerate(NEEDED):
    raw = RAW_GLYPHS[char]
    rotated = rotate_90cw(raw)
    rotated_glyphs[char] = rotated
    new_glyph_indices[char] = N_ORIG_GLYPHS + i
    print(f"\n'{char}' → glyph {new_glyph_indices[char]}")
    show_glyph(rotated)

print(f"\nNew glyph assignments: {new_glyph_indices}")

# Glyph code for each char:  0x0041='A', 0x0020=' ', etc. (direct ASCII Unicode)
# We'll output these chars in the script using opcode 05 + direct glyph index
# The glyph indices 95-103 fit in a u16 positive value.
# So we store: 05 + pack_u16_le(glyph_index)
# Unlike the original chars which used negative indices (U+FFF9..FFFE),
# we use positive direct indices.


# ── Step 2: Patch the NFTR font file ─────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Patching NFTR font (ID05585.bin)")
print("=" * 60)

font_data = bytearray(FONT_IN.read_bytes())
print(f"Original size: {len(font_data)} bytes, {N_ORIG_GLYPHS} glyphs")

# Build new glyph bytes (appended at PLGC_END = 0x3ac)
new_glyph_block = bytearray()
for char in NEEDED:
    new_glyph_block += rotated_glyphs[char]

print(f"Adding {len(NEEDED)} glyphs = {len(new_glyph_block)} bytes at offset {hex(PLGC_END)}")

# Insert at PLGC_END
new_font = bytearray(font_data[:PLGC_END] + new_glyph_block + font_data[PLGC_END:])

# Update file size in NFTR header (at bytes 8-11)
struct.pack_into('<I', new_font, 8, len(new_font))

# Update PLGC section size (at PLGC_START+4..7)
old_plgc_sz = struct.unpack_from('<I', new_font, PLGC_START + 4)[0]
new_plgc_sz = old_plgc_sz + len(new_glyph_block)
struct.pack_into('<I', new_font, PLGC_START + 4, new_plgc_sz)
print(f"PLGC size: {old_plgc_sz} → {new_plgc_sz}")

# Update FINF section pointers that reference data AFTER insert point
# FINF is at 0x10; its data starts at FINF+8=0x18
# Pointer fields are at file offsets 0x10+16=0x20, 0x10+20=0x24, 0x10+24=0x28
INSERT_LEN = len(new_glyph_block)
for field_abs, name in [(0x20, "FINF.tglp_ptr"), (0x24, "FINF.cmap1_ptr"), (0x28, "FINF.cmap2_ptr")]:
    v = struct.unpack_from('<I', new_font, field_abs)[0]
    if v >= PLGC_END:
        struct.pack_into('<I', new_font, field_abs, v + INSERT_LEN)
        print(f"  {name}: {hex(v)} → {hex(v + INSERT_LEN)}")

print(f"New font size: {len(new_font)} bytes")
FONT_OUT.write_bytes(new_font)
print(f"✅ Saved → {FONT_OUT}")


# ── Step 3: Patch the script bytecode ────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3: Patching script (ID04167.bin)")
print("=" * 60)

script_data = bytearray(SCRIPT_IN.read_bytes())
bc = script_data[BC_OFFSET:]

# Original sequence at bc+0x50:
# 07 [05 F9FF] [05 FAFF] [05 FBFF] [05 FCFF] [05 FDFF] [05 FEFF]
# = 1 + 6*3 = 19 bytes
# Glyphs 88..93 = the "...夢？" text

ORIG_SEQ_OFF  = BC_OFFSET + TEXT_OPCODE_OFF  # file offset = 0x714 + 0x50 = 0x764
ORIG_SEQ_LEN  = 19  # 1 opcode byte + 6 × (1+2) char bytes

orig_seq = script_data[ORIG_SEQ_OFF : ORIG_SEQ_OFF + ORIG_SEQ_LEN]
print(f"Original sequence at file+{ORIG_SEQ_OFF:x}:")
print(f"  {orig_seq.hex()}")

# Decode the original sequence
i = 0
print("  Decoded:")
while i < len(orig_seq):
    op = orig_seq[i]
    if op == 0x07:
        print(f"    op 0x07 (begin output sequence)")
        i += 1
    elif op == 0x05 and i+2 < len(orig_seq):
        code = struct.unpack_from('<H', orig_seq, i+1)[0]
        signed = struct.unpack('<h', struct.pack('<H', code))[0]
        glyph = 95 + signed if signed < 0 else code
        print(f"    05 U+{code:04X} → glyph {glyph}")
        i += 3
    else:
        print(f"    {op:02x}")
        i += 1

# Build replacement sequence for "A dream...?"
# Translation: ['A', ' ', 'd', 'r', 'e', 'a', 'm', '.', '.', '.', '?']
TRANSLATION = "A dream...?"
TRANS_GLYPHS = [new_glyph_indices.get(c, new_glyph_indices.get('?')) for c in TRANSLATION]
print(f"\nTranslation: {TRANSLATION!r}")
print(f"Glyph indices: {TRANS_GLYPHS}")

# Build new bytecode sequence
# We must fit in the same space (19 bytes) or handle length mismatch
# Original: 19 bytes (1 opcode + 6 chars)
# New: 1 + 11×3 = 34 bytes — too long!
# 
# Options:
# A) Use a compact encoding (if the game supports it)
# B) Overwrite more bytes (shift data)
# C) Use only 6 glyphs (reduce translation) → "dream?"
# D) Use a different font style where 3 chars combine
#
# For now, let's use option C: shorten to 6 glyphs that still convey the meaning.
# "A dream?" = 8 chars → still 25 bytes > 19
# 
# Better option: Replace the ENTIRE text sequence. Let's check what comes AFTER bc+0x62.
# After the 6-char sequence: look at bc+0x63..
print(f"\nBytes after original sequence (bc+{TEXT_OPCODE_OFF+ORIG_SEQ_LEN:x}):")
post = bc[TEXT_OPCODE_OFF + ORIG_SEQ_LEN : TEXT_OPCODE_OFF + ORIG_SEQ_LEN + 20]
print(f"  {post.hex()}")

# The bytes after: 20 08 28 90 e3 00 07 02 e4...
# 0x20 = SPACE? No, 0x20 as an opcode. Let's not overwrite those.
# 
# STRATEGY: We have 19 bytes to use. 
# "A dream?" in 6 glyphs doesn't work letter-by-letter.
# But we can use the EXISTING glyphs creatively:
# The game already has glyphs. We're ADDING new ones.
# 
# Actually: let's just EXPAND the sequence. The bytecode can be shifted.
# The script header has an offset to the bytecode section (at file offset 10-13 = 0x714).
# If we insert bytes into the bytecode, we just need to make sure the opcodes still work.
# 
# The key question: does the script header table reference offsets within the bytecode?
# Looking at the header table pattern, yes it likely does. Shifting would break those references.
# 
# BETTER STRATEGY: Overwrite more bytes but ensure we don't corrupt the next valid opcode.
# The bytes at bc+0x63: 20 08 28 90 e3 00 07 02 e4 6e 25 02 07...
# 0x20 = space in ASCII, but also a valid opcode value
# Let's check: does 0x20 = a known opcode?
# Pattern: 20 08 28 90 = 4 bytes. If opcode 0x20 takes 3 args = 20 08 28 90
# Then: e3 00 = maybe 2-byte opcode? 07 02 e4 = opcode 07 with payload?
# 
# For now, use just 5 chars: "dream" or abbreviate.
# Actually: let's use 6 glyphs for "dream?" 
# But 6 glyphs won't include 'A ' at start.
# 
# FINAL APPROACH: 
# Use the original 19-byte slot for 6 chars: glyph indices 95-103
# Pick 6 most important chars from "A dream...?"
# "dream?" = 6 chars (d, r, e, a, m, ?)
# OR: "A dream" = 7 chars = 22 bytes (3 bytes over budget)
# 
# Let's check how many bytes follow that are "safe" to overwrite:
# bc+0x63: 20 08 28 90 e3 = 5 extra bytes (for total of 24 bytes available)
# With 24 bytes: opcode(1) + 7×char(3) = 22 bytes = 7 chars = "A dream"
# 
# Check: if we overwrite bc+0x63..0x66 (4 bytes of "20 08 28 90")
# what happens? We need to know what opcode 0x20 is.

print(f"\nChecking 24-byte slot for replacement:")
print(f"Available: 19 + 5 = 24 bytes")
print(f"'A dream.?' = 9 chars × 3 bytes + 1 opcode = 28 bytes (too many)")
print(f"'A dream'   = 7 chars × 3 bytes + 1 opcode = 22 bytes ✓")
print(f"'dream...?' = 9 chars = 28 bytes (too many)")

# Use 7 chars: "A dream " (with trailing space to use full 24 bytes)
TRANSLATION_SHORT = "A dream"
TRANS_GLYPHS_SHORT = [new_glyph_indices[c] for c in TRANSLATION_SHORT]
print(f"\nUsing translation: {TRANSLATION_SHORT!r}")
print(f"Glyph indices: {TRANS_GLYPHS_SHORT}")

# Build 22-byte sequence (1 opcode + 7 chars)
new_seq = bytearray([0x07])  # opcode: output sequence
for gidx in TRANS_GLYPHS_SHORT:
    new_seq += bytes([0x05]) + struct.pack('<H', gidx)
print(f"New sequence ({len(new_seq)} bytes): {new_seq.hex()}")

# We need to pad to 22 bytes (fill remaining with NOPs or keep next opcode)
# Actually: let's just write the 22 bytes and leave the next bytes unchanged
# The space saved (we have 22 out of 24 available): the last 2 bytes (0x28 0x90) 
# must now look like valid opcodes. These were the 3rd and 4th byte of opcode 0x20.
# If we cut into opcode 0x20's args, that would corrupt it.
# 
# SAFER: Write exactly 19 bytes (same as original), use only 6 chars.
# Use "Adream" = 6 chars, no space (or use space as separator)
# "Adream" isn't great. Let's use "dream?" or "A drm?" or just test with 5.

# Actually let me just write 19 bytes and use "dream?" (6 chars minus space):
# No - that loses the 'A'. Let's use "A drm?" = 6 chars (still conveys dream/question)

# ACTUAL BEST APPROACH: Use all 95+9 glyphs, write the FULL "A dream...?" 
# using 34 bytes, and patch the script to accommodate by adjusting surrounding NOPs.
# 
# Let's look for free space (NOP-like opcodes) around the target area.
print(f"\n=== Surrounding bytecode (bc+0x3c..0x80) ===")
for pos in range(0x3c, 0x80):
    op = bc[pos]
    print(f"  bc+{pos:04x}: {op:02x}", end="")
    if op == 0x05 and pos+2 < len(bc):
        code = struct.unpack_from('<H', bc, pos+1)[0]
        print(f" [CHAR U+{code:04X}]", end="")
    elif op == 0x07: print(f" [BEGIN_SEQ]", end="")
    elif op == 0x6e: print(f" [OP_6E]", end="")
    elif op == 0x09: print(f" [OP_09]", end="")
    elif op == 0x02: print(f" [OP_02]", end="")
    elif op == 0x00: print(f" [NOP]", end="")
    print()

print("\nDone - check output to decide exact replacement strategy")

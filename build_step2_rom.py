#!/usr/bin/env python3
"""
build_step2_rom.py - Build the Sigma Harmonics Step 2 test ROM
================================================================
CORRECT APPROACH (v4):
  - Glyphs 22-26 (file offset 302-346, > 256 bytes) are used for English chars
    This avoids the CRILAYLA back-reference-to-zero-padding bug that affected
    glyphs 15-19 (file offset 225-269, within the first 256 bytes = CRILAYLA prefix)
  - The scene script in ID04167.bin is patched to use indices 22-26 (absolute)
    instead of -6 to -2 (relative from 21)

First dialog line "。。。夢？" → 5 English glyph slots = "dream"
Script opcodes changed from: 05 FA FF 05 FB FF 05 FC FF 05 FD FF 05 FE FF
                          to: 05 16 00 05 17 00 05 18 00 05 19 00 05 1A 00
"""

import sys, struct
from pathlib import Path

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module, cmp_cri

# ── Config ────────────────────────────────────────────────────────────────────
ORIG_ROM   = Path("2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds")
ARM9_PATCH = Path("ghidra_workspace/arm9_step1.bin")
OUT_ROM    = Path("sigma_step2_v2.nds")

GLYPH_START = 60   # NFTR CGLP glyphs start at byte 60
GLYPH_LEN   = 11   # 11 bytes per glyph: [bx(1)][w(1)][row0-row8(9)]

# Glyph indices 22-26 are at file offsets 302-346 (safely > 256 bytes into file)
# This ensures CRILAYLA encodes them in the compressed payload without
# back-references into the zero-padding region of the 15680-byte CPK slot.
TARGET_GLYPHS = [22, 23, 24, 25, 26]  # = 0x16, 0x17, 0x18, 0x19, 0x1A
TARGET_CHARS  = ['d', 'r', 'e', 'a', 'm']

# Scene script patch locations (in ID04167.bin)
# The first dialog line opcodes are at offset 0x011C in ID04167.bin:
#   05 FA FF = draw glyph -6 (= glyph 15) → replace with 05 16 00 = glyph 22
SCRIPT_FILE_ID   = 4167   # ID04167
SCRIPT_PATCH_SEQ_OLD = bytes([0x05, 0xFA, 0xFF,  # glyph -6
                               0x05, 0xFB, 0xFF,  # glyph -5
                               0x05, 0xFC, 0xFF,  # glyph -4
                               0x05, 0xFD, 0xFF,  # glyph -3
                               0x05, 0xFE, 0xFF]) # glyph -2
SCRIPT_PATCH_SEQ_NEW = bytes([0x05, 0x16, 0x00,  # glyph 22 = 'd'
                               0x05, 0x17, 0x00,  # glyph 23 = 'r'
                               0x05, 0x18, 0x00,  # glyph 24 = 'e'
                               0x05, 0x19, 0x00,  # glyph 25 = 'a'
                               0x05, 0x1A, 0x00]) # glyph 26 = 'm'

# ── Glyph bitmaps ─────────────────────────────────────────────────────────────
def rotate_90cw(rows_9bytes):
    """Rotate 8x9 glyph 90° clockwise (pre-rotate for book mode display)."""
    src = [[0]*8 for _ in range(9)]
    for r in range(9):
        for c in range(8):
            src[r][c] = (rows_9bytes[r] >> (7-c)) & 1
    result = bytearray(9)
    for c in range(8):
        byte = 0
        for r in range(9):
            if src[r][c]:
                byte |= (1 << (8-r))
        result[c] = byte
    result[8] = 0
    return bytes(result)

# 8x9 1bpp upright pixel font chars (appear upright, then rotated CW for book mode)
GLYPH_BITMAPS = {
    'd': bytes([0x00, 0x04, 0x04, 0x3c, 0x44, 0x44, 0x44, 0x3c, 0x00]),
    'r': bytes([0x00, 0x00, 0x5c, 0x60, 0x40, 0x40, 0x40, 0x00, 0x00]),
    'e': bytes([0x00, 0x00, 0x38, 0x44, 0x7c, 0x40, 0x38, 0x00, 0x00]),
    'a': bytes([0x00, 0x00, 0x38, 0x04, 0x3c, 0x44, 0x3c, 0x00, 0x00]),
    'm': bytes([0x00, 0x00, 0x68, 0x54, 0x54, 0x44, 0x44, 0x00, 0x00]),
}

# ── Load ROM ──────────────────────────────────────────────────────────────────
print(f"Loading ROM: {ORIG_ROM}")
rom = bytearray(ORIG_ROM.read_bytes())
print(f"  ROM size: {len(rom):,} bytes")

# ── Find CPK ──────────────────────────────────────────────────────────────────
fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start  = struct.unpack_from('<I', rom, fat_offset)[0]
cpk_end    = struct.unpack_from('<I', rom, fat_offset+4)[0]
print(f"  CPK at ROM+{hex(cpk_start)}..{hex(cpk_end)} ({cpk_end-cpk_start:,} bytes)")

cpk_data = bytearray(rom[cpk_start:cpk_end])

# Parse CPK file table
cpk_temp = '/tmp/build_step2.cpk'
open(cpk_temp, 'wb').write(cpk_data)
c = cpk_module.readCPK(cpk_temp)
file_entries = {e.id: e for e in c.filetable if hasattr(e, 'id') and e.filetype == "FILE"}
print(f"  CPK has {len(file_entries)} file entries")

# ── PATCH 1: Font ID05585 (English glyph bitmaps at indices 22-26) ────────────
print(f"\nPatching font ID05585 (glyphs 22-26 = 'dream')...")

e5585 = file_entries.get(5585)
if e5585 is None:
    print("  ❌ ID05585 not found in CPK!")
    sys.exit(1)

slot_size = e5585.filesize
orig_slot = bytearray(rom[cpk_start + e5585.fileoffset : cpk_start + e5585.fileoffset + slot_size])
print(f"  CPK slot size: {slot_size} bytes")

# Decompress original slot to get the real font data
orig_slot_cri = bytearray(orig_slot)
orig_slot_cri[:8] = b'CRILAYLA'
font_data = bytearray(cmp_cri.decompressCRILAYLA(bytes(orig_slot_cri)))
print(f"  Decompressed font: {len(font_data)} bytes")

# Apply English glyph bitmaps at indices 22-26
for glyph_idx, char in zip(TARGET_GLYPHS, TARGET_CHARS):
    off = GLYPH_START + glyph_idx * GLYPH_LEN
    assert off > 256, f"Glyph {glyph_idx} offset {off} is in CRILAYLA prefix zone!"
    rotated = rotate_90cw(GLYPH_BITMAPS[char])
    new_glyph = bytes([0, 8]) + rotated
    font_data[off:off+GLYPH_LEN] = new_glyph
    print(f"  Glyph {glyph_idx} ('{char}') @ offset {off}: {new_glyph.hex()}")

# Recompress
compressed = cmp_cri.compressCRILAYLA(bytes(font_data))
payload = compressed[16:]
print(f"  Recompressed: {len(compressed)} bytes, payload: {len(payload)} bytes")

# Verify in slot context (simulating the actual game CPK loading)
verify_slot = bytearray(slot_size)
verify_slot[:8] = b'CRILAYLA'
verify_slot[8:12] = orig_slot[8:12]  # keep original uncomp_sz
struct.pack_into('<I', verify_slot, 12, len(payload))
verify_slot[slot_size - len(payload):] = payload
verify_dec = cmp_cri.decompressCRILAYLA(bytes(verify_slot))
all_ok = True
for glyph_idx, char in zip(TARGET_GLYPHS, TARGET_CHARS):
    off = GLYPH_START + glyph_idx * GLYPH_LEN
    raw = verify_dec[off:off+GLYPH_LEN]
    exp = bytes(font_data[off:off+GLYPH_LEN])
    ok = raw == exp
    print(f"  {'✅' if ok else '❌'} Glyph {glyph_idx} ('{char}'): {raw.hex()}")
    if not ok: all_ok = False
if not all_ok:
    print("  ❌ Slot-context verification failed! Aborting.")
    sys.exit(1)
print("  ✅ Slot-context verification passed!")

# Build and inject the new slot
if len(payload) > slot_size - 16:
    print("  ❌ Payload too large!")
    sys.exit(1)
new_slot = bytearray(slot_size)
new_slot[0:8]  = b'\x00' * 8         # zeroed magic (game restores at runtime)
new_slot[8:12] = orig_slot[8:12]     # preserve original uncomp_sz
struct.pack_into('<I', new_slot, 12, len(payload))
new_slot[slot_size - len(payload):] = payload
cpk_data[e5585.fileoffset : e5585.fileoffset + slot_size] = new_slot
print(f"  ✅ Font slot updated at CPK+{hex(e5585.fileoffset)}")

# ── PATCH 2: Scene script ID04167 (update glyph indices to 22-26) ─────────────
print(f"\nPatching scene script ID04167 (glyph indices -6..-2 → 22..26)...")

e4167 = file_entries.get(SCRIPT_FILE_ID)
if e4167 is None:
    print(f"  ❌ ID{SCRIPT_FILE_ID:05d} not found in CPK!")
    sys.exit(1)

script_slot_size = e4167.filesize
script_orig_slot = bytearray(rom[cpk_start + e4167.fileoffset : cpk_start + e4167.fileoffset + script_slot_size])
print(f"  Script slot size: {script_slot_size} bytes")

# Decompress the script
script_slot_cri = bytearray(script_orig_slot)
script_slot_cri[:8] = b'CRILAYLA'
script_data = bytearray(cmp_cri.decompressCRILAYLA(bytes(script_slot_cri)))
print(f"  Decompressed script: {len(script_data)} bytes")

# Find and replace the opcode sequence
pos = bytes(script_data).find(SCRIPT_PATCH_SEQ_OLD)
if pos < 0:
    print("  ❌ Old opcode sequence NOT found in decompressed script!")
    print(f"  Looking for: {SCRIPT_PATCH_SEQ_OLD.hex()}")
    sys.exit(1)
print(f"  Found opcodes at script offset +{pos} (0x{pos:04x})")
print(f"  Old: {SCRIPT_PATCH_SEQ_OLD.hex()}")
print(f"  New: {SCRIPT_PATCH_SEQ_NEW.hex()}")
assert pos > 256, f"Opcode at offset {pos} is in CRILAYLA prefix zone!"
script_data[pos:pos+len(SCRIPT_PATCH_SEQ_NEW)] = SCRIPT_PATCH_SEQ_NEW

# Recompress the patched script
script_compressed = cmp_cri.compressCRILAYLA(bytes(script_data))
script_payload = script_compressed[16:]
print(f"  Recompressed: {len(script_compressed)} bytes, payload: {len(script_payload)} bytes")

if len(script_payload) > script_slot_size - 16:
    print("  ❌ Script payload too large!")
    sys.exit(1)

# Verify in slot context
verify_script_slot = bytearray(script_slot_size)
verify_script_slot[:8] = b'CRILAYLA'
verify_script_slot[8:12] = script_orig_slot[8:12]
struct.pack_into('<I', verify_script_slot, 12, len(script_payload))
verify_script_slot[script_slot_size - len(script_payload):] = script_payload
verify_script_dec = cmp_cri.decompressCRILAYLA(bytes(verify_script_slot))
verify_pos = bytes(verify_script_dec).find(SCRIPT_PATCH_SEQ_NEW)
if verify_pos < 0:
    print("  ❌ Script slot-context verification failed!")
    sys.exit(1)
print(f"  ✅ New opcodes verified at script offset {verify_pos}")

# Inject script into CPK
new_script_slot = bytearray(script_slot_size)
new_script_slot[0:8]  = b'\x00' * 8
new_script_slot[8:12] = script_orig_slot[8:12]
struct.pack_into('<I', new_script_slot, 12, len(script_payload))
new_script_slot[script_slot_size - len(script_payload):] = script_payload
cpk_data[e4167.fileoffset : e4167.fileoffset + script_slot_size] = new_script_slot
print(f"  ✅ Script slot updated at CPK+{hex(e4167.fileoffset)}")

# ── Write CPK back into ROM ───────────────────────────────────────────────────
print(f"\nWriting modified CPK back to ROM...")
rom[cpk_start:cpk_end] = cpk_data
print(f"  ✅ CPK updated")

# ── PATCH 3: ARM9 (Step 1 textbox position patch) ─────────────────────────────
print(f"\nInjecting patched ARM9 (Step 1 textbox position)...")
arm9_new  = ARM9_PATCH.read_bytes()
arm9_off  = struct.unpack_from('<I', rom, 0x20)[0]
arm9_size = struct.unpack_from('<I', rom, 0x2c)[0]
print(f"  ARM9: {arm9_size:,} bytes at ROM+{hex(arm9_off)}")
if len(arm9_new) != arm9_size:
    struct.pack_into('<I', rom, 0x2c, len(arm9_new))
rom[arm9_off : arm9_off + len(arm9_new)] = arm9_new
print(f"  ✅ ARM9 injected")

# ── Write output ROM ──────────────────────────────────────────────────────────
print(f"\nWriting output ROM: {OUT_ROM}")
OUT_ROM.write_bytes(rom)
print(f"  ✅ ROM written: {len(rom):,} bytes")

print(f"\n✅ Done! Test ROM: {OUT_ROM.resolve()}")
print(f"   English glyphs 'd','r','e','a','m' at font indices 22-26")
print(f"   Scene script patched to reference those indices")
print(f"   ARM9 Step 1 textbox position patch applied")

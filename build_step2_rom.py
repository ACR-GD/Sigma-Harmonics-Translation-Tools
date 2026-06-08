#!/usr/bin/env python3
"""
build_step2_rom.py - Build the Sigma Harmonics Step 2 test ROM

This script:
  1. Applies Step 1 patch (textbox position) to arm9.bin
  2. Applies Step 2 patch (English glyphs) to ID05585.bin (font)
  3. Recompresses the patched font with CRILAYLA
  4. Injects the compressed font and patched arm9 into a new ROM

Usage:
    /usr/bin/python3 build_step2_rom.py
"""

import sys, struct, os, glob
from pathlib import Path

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module, cmp_cri

# ── Config ────────────────────────────────────────────────────────────────────
ORIG_ROM   = Path("2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds")
ARM9_PATCH = Path("ghidra_workspace/arm9_step1.bin")
FONT_PATCH = Path("modified_cpk/ID05585.bin")  # our patched raw NFTR
OUT_ROM    = Path("sigma_step2_v2.nds")

BASE = 0x02000000

# ── Load ROM ──────────────────────────────────────────────────────────────────
print(f"Loading ROM: {ORIG_ROM}")
rom = bytearray(ORIG_ROM.read_bytes())
print(f"  ROM size: {len(rom):,} bytes")

# ── Find CPK ─────────────────────────────────────────────────────────────────
fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start  = struct.unpack_from('<I', rom, fat_offset)[0]
cpk_end    = struct.unpack_from('<I', rom, fat_offset+4)[0]
print(f"  CPK at ROM+{hex(cpk_start)}..{hex(cpk_end)} ({cpk_end-cpk_start:,} bytes)")

cpk_data = bytearray(rom[cpk_start:cpk_end])

# ── Parse CPK file table ───────────────────────────────────────────────────────
cpk_temp = '/tmp/build_step2.cpk'
open(cpk_temp, 'wb').write(cpk_data)
c = cpk_module.readCPK(cpk_temp)
file_entries = {e.id: e for e in c.filetable if hasattr(e, 'id') and e.filetype == "FILE"}
print(f"  CPK has {len(file_entries)} file entries")

# ── Patch font ID05585 ────────────────────────────────────────────────────────
print(f"\nPatching font ID05585 (English 'dream?' glyphs)...")
raw_nftr = FONT_PATCH.read_bytes()
print(f"  Raw NFTR: {len(raw_nftr)} bytes")

# Compress with CRILAYLA
compressed = cmp_cri.compressCRILAYLA(raw_nftr)
print(f"  Compressed: {len(compressed)} bytes")

# Verify round-trip
dec_check = cmp_cri.decompressCRILAYLA(compressed)
assert dec_check == raw_nftr, "Compression round-trip FAILED!"
print(f"  ✅ Compression verified")

e5585 = file_entries.get(5585)
if e5585 is None:
    print("  ❌ ID05585 not found in CPK!")
    sys.exit(1)

slot_size = e5585.filesize
print(f"  CPK slot size: {slot_size} bytes, our compressed: {len(compressed)} bytes")

our_payload = compressed[16:]  # compressed data without the 16-byte header
our_comp_sz = struct.unpack_from('<I', bytearray(compressed), 12)[0]
print(f"  Compressed payload: {len(our_payload)} bytes (declared comp_sz={our_comp_sz})")

if len(our_payload) > slot_size - 16:
    print(f"  ❌ PAYLOAD TOO LARGE for slot!")
    sys.exit(1)

# Read original slot to get header fields (uncomp_sz etc.)
orig_slot = bytearray(rom[cpk_start + e5585.fileoffset : cpk_start + e5585.fileoffset + slot_size])

# CRILAYLA decompressor reads backwards from the END of the buffer.
# Correct layout: [header(16)][zero padding][payload at END]
new_slot = bytearray(slot_size)
new_slot[0:8]  = b'\x00' * 8        # zeroed magic (restored by game at runtime)
new_slot[8:12] = orig_slot[8:12]    # keep original uncomp_sz field
struct.pack_into('<I', new_slot, 12, our_comp_sz)  # update comp_sz field

# Place payload at the END of the slot
payload_start = slot_size - len(our_payload)
new_slot[payload_start:] = our_payload
print(f"  Payload placed at slot[{payload_start}:{slot_size}]")

cpk_data[e5585.fileoffset : e5585.fileoffset + slot_size] = new_slot
print(f"  ✅ Font injected into CPK slot at {hex(e5585.fileoffset)}")

# ── Write modified CPK back into ROM ─────────────────────────────────────────
print(f"\nWriting modified CPK back into ROM...")
rom[cpk_start:cpk_end] = cpk_data
print(f"  ✅ CPK updated")

# ── Patch ARM9 (Step 1: textbox position) ────────────────────────────────────
print(f"\nInjecting patched ARM9 (Step 1: textbox position)...")
arm9_new  = ARM9_PATCH.read_bytes()
arm9_off  = struct.unpack_from('<I', rom, 0x20)[0]
arm9_size = struct.unpack_from('<I', rom, 0x2c)[0]
print(f"  Original ARM9: {arm9_size:,} bytes at ROM+{hex(arm9_off)}")
print(f"  Patched ARM9:  {len(arm9_new):,} bytes")

if len(arm9_new) != arm9_size:
    print(f"  ⚠️  Size mismatch! Updating header...")
    struct.pack_into('<I', rom, 0x2c, len(arm9_new))

rom[arm9_off : arm9_off + len(arm9_new)] = arm9_new
print(f"  ✅ ARM9 injected")

# ── Write output ROM ──────────────────────────────────────────────────────────
print(f"\nWriting output ROM: {OUT_ROM}")
OUT_ROM.write_bytes(rom)
print(f"  ✅ ROM written: {len(rom):,} bytes")

# ── Quick verification ────────────────────────────────────────────────────────
print(f"\nVerification:")
rom_check = OUT_ROM.read_bytes()

# Check ARM9 patch
off = struct.unpack_from('<I', bytearray(rom_check), 0x20)[0]
arm9_in_rom = rom_check[off:off+32]
print(f"  ARM9 start: {arm9_in_rom[:16].hex()}")

# Check font in CPK
cpk_check = rom_check[cpk_start:cpk_end]
e = e5585
font_in_rom = cpk_check[e.fileoffset:e.fileoffset+e.filesize]
print(f"  Font first 16: {font_in_rom[:16].hex()}")
# Decompress and check glyph 88
try:
    buf = bytearray(font_in_rom[:e.filesize])
    buf[:8] = b'CRILAYLA'
    dec_font = cmp_cri.decompressCRILAYLA(bytes(buf))
    glyph_88 = dec_font[0x50 + 88*9 : 0x50 + 88*9 + 9]
    expected = bytes.fromhex('001c2222223f000000')  # our 'd' glyph
    if glyph_88 == expected:
        print(f"  ✅ Glyph 88 ('d') is correct in ROM!")
    else:
        print(f"  ❌ Glyph 88 mismatch: got {glyph_88.hex()}, expected {expected.hex()}")
except Exception as ex:
    print(f"  ⚠️  Verification failed: {ex}")

print(f"\n✅ Done! Test ROM: {OUT_ROM.resolve()}")

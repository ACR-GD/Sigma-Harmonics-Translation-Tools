#!/usr/bin/env python3
"""Deep diagnosis: compare rebuilt CPK against original, file by file."""
import struct
import sys
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
PATCHED_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"

# Read both ROMs
with open(ORIG_ROM, 'rb') as f:
    orig_rom = f.read()
with open(PATCHED_ROM, 'rb') as f:
    patched_rom = f.read()

# Get CPK locations from FAT
fat_off = struct.unpack_from('<I', orig_rom, 0x48)[0]
orig_cpk_start = struct.unpack_from('<I', orig_rom, fat_off)[0]
orig_cpk_end = struct.unpack_from('<I', orig_rom, fat_off + 4)[0]

pat_cpk_start = struct.unpack_from('<I', patched_rom, fat_off)[0]
pat_cpk_end = struct.unpack_from('<I', patched_rom, fat_off + 4)[0]

orig_cpk = orig_rom[orig_cpk_start:orig_cpk_end]
pat_cpk = patched_rom[pat_cpk_start:pat_cpk_end]

# Parse original CPK to get file table
cpk_temp = "/tmp/sigma_diag.cpk"
with open(cpk_temp, 'wb') as f:
    f.write(orig_cpk)
cpk_obj = cpk_module.readCPK(cpk_temp)

file_entries = sorted(
    [e for e in cpk_obj.filetable if e.filetype == "FILE"],
    key=lambda e: e.fileoffset
)

print(f"Original CPK: {len(orig_cpk):,} bytes, {len(file_entries)} files")
print(f"Patched CPK:  {len(pat_cpk):,} bytes")
print()

# Check first 10 files and any modified files
print("=== First 10 files comparison ===")
modified_ids = set()
import os
for fname in os.listdir("/Users/acr/Develop/sigma-harmonics/modified_cpk/"):
    if fname.endswith('.bin'):
        try:
            modified_ids.add(int(fname.replace('ID','').replace('.bin','')))
        except: pass

issues = 0
for i, entry in enumerate(file_entries[:20]):
    fid = entry.id
    off = entry.fileoffset  # offset within CPK file
    sz = entry.filesize
    ext_sz = entry.extractsize
    
    orig_data = orig_cpk[off:off+sz]
    
    # Check what the data starts with
    orig_header = orig_data[:8] if len(orig_data) >= 8 else orig_data
    is_compressed = (orig_header[:8] == b'\x00'*8 and sz != ext_sz)
    
    # In patched CPK, check the same offset range
    pat_data = pat_cpk[off:off+sz] if off+sz <= len(pat_cpk) else b''
    
    status = "MATCH" if orig_data == pat_data else "DIFF"
    mod = "MOD" if fid in modified_ids else "   "
    comp = "COMP" if is_compressed else "RAW "
    
    if status == "DIFF" or i < 10:
        print(f"  File {fid:5d} [{mod}] [{comp}] off=0x{off:X} sz={sz:6d} ext={ext_sz:6d} | "
              f"orig_hdr={orig_header[:8].hex()} | {status}")
        if status == "DIFF" and fid not in modified_ids:
            issues += 1
            # Show what differs
            pat_header = pat_data[:8] if len(pat_data) >= 8 else pat_data
            print(f"    ^^^ UNEXPECTED DIFF! pat_hdr={pat_header.hex()}")

print(f"\n=== Checking ALL unmodified files for corruption ===")
corrupt_count = 0
offset_mismatch = 0

# Rebuild offsets the same way our builder does
content_offset = 2048
align_val = 512
rebuild_offset = content_offset

for i, entry in enumerate(file_entries):
    fid = entry.id
    off = entry.fileoffset
    sz = entry.filesize
    
    # Check if original file at original offset matches patched file at rebuilt offset
    orig_data = orig_cpk[off:off+sz]
    
    if fid in modified_ids:
        # Modified file - check the rebuilt position
        mod_path = f"/Users/acr/Develop/sigma-harmonics/modified_cpk/ID{fid:05d}.bin"
        with open(mod_path, 'rb') as f:
            mod_data = f.read()
        pat_data_at_rebuild = pat_cpk[rebuild_offset:rebuild_offset+len(mod_data)]
        if pat_data_at_rebuild != mod_data:
            print(f"  ID{fid:05d} MOD: data mismatch at rebuild_off=0x{rebuild_offset:X}")
            corrupt_count += 1
        rebuild_offset += len(mod_data)
    else:
        pat_data_at_rebuild = pat_cpk[rebuild_offset:rebuild_offset+sz]
        if pat_data_at_rebuild != orig_data:
            if corrupt_count < 5:
                print(f"  ID{fid:05d}: CORRUPT at rebuild_off=0x{rebuild_offset:X} (orig_off=0x{off:X})")
                print(f"    orig[:16]={orig_data[:16].hex()}")
                print(f"    pat[:16] ={pat_data_at_rebuild[:16].hex()}")
            corrupt_count += 1
        rebuild_offset += sz
    
    # Check if our offset matches original offset
    if rebuild_offset != off + sz and fid not in modified_ids:
        if offset_mismatch == 0:
            print(f"\n  First offset divergence at file {fid}: expected end 0x{off+sz:X}, got 0x{rebuild_offset:X}")
        offset_mismatch += 1
    
    # Align
    if i + 1 < len(file_entries):
        remainder = (rebuild_offset - content_offset) % align_val
        if remainder > 0:
            rebuild_offset += (align_val - remainder)

print(f"\n=== Summary ===")
print(f"  Corrupted unmodified files: {corrupt_count}")
print(f"  Offset mismatches: {offset_mismatch}")
print(f"  Modified file IDs: {len(modified_ids)}")

# Also verify: does the original ROM itself work?
# Let's just copy it and tell user to test
import shutil
test_copy = "/Users/acr/Develop/sigma-harmonics/test_original_copy.nds"
if not os.path.exists(test_copy):
    shutil.copy2(ORIG_ROM, test_copy)
    print(f"\n  Created test copy of original ROM: {test_copy}")
    print(f"  >>> Please test this in MelonDS to confirm the original ROM works! <<<")

import os
os.remove(cpk_temp)

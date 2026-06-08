#!/usr/bin/env python3
"""
Check if modified files were originally compressed and what sizes we need.
"""
import struct
import sys
import os
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"
EXTRACTED_DIR = "/Users/acr/Develop/sigma-harmonics/extracted_cpk/"

with open(ORIG_ROM, 'rb') as f:
    rom = f.read()

fat_off = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start = struct.unpack_from('<I', rom, fat_off)[0]
cpk_end = struct.unpack_from('<I', rom, fat_off + 4)[0]
orig_cpk = rom[cpk_start:cpk_end]

cpk_temp = "/tmp/sigma_diag2.cpk"
with open(cpk_temp, 'wb') as f:
    f.write(orig_cpk)
cpk_obj = cpk_module.readCPK(cpk_temp)

file_entries = sorted(
    [e for e in cpk_obj.filetable if e.filetype == "FILE"],
    key=lambda e: e.fileoffset
)

# Build ID lookup
id_to_entry = {e.id: e for e in file_entries}

# Check modified files
modified_ids = set()
for fname in os.listdir(MODIFIED_DIR):
    if fname.endswith('.bin'):
        try:
            modified_ids.add(int(fname.replace('ID','').replace('.bin','')))
        except: pass

print(f"Modified files: {len(modified_ids)}")
print(f"\nFile ID | Orig FileSize | Orig ExtractSize | Compressed? | Mod Size | Extracted Size | Header (orig)")
print("-" * 120)

for fid in sorted(modified_ids)[:20]:
    entry = id_to_entry.get(fid)
    if not entry:
        continue
    
    mod_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
    ext_path = os.path.join(EXTRACTED_DIR, f"ID{fid:05d}.bin")
    
    mod_size = os.path.getsize(mod_path) if os.path.exists(mod_path) else 0
    ext_size = os.path.getsize(ext_path) if os.path.exists(ext_path) else 0
    
    # Check original data header
    orig_data = orig_cpk[entry.fileoffset:entry.fileoffset+16]
    is_compressed = entry.filesize != entry.extractsize
    
    print(f"  {fid:5d}   | {entry.filesize:13,} | {entry.extractsize:16,} | {'YES':11s} | {mod_size:8,} | {ext_size:14,} | {orig_data[:8].hex()}")

print(f"\n... showing first 20 of {len(modified_ids)}")

# Key question: how many modified files are compressed vs raw?
comp_count = 0
raw_count = 0
for fid in modified_ids:
    entry = id_to_entry.get(fid)
    if entry and entry.filesize != entry.extractsize:
        comp_count += 1
    else:
        raw_count += 1

print(f"\nCompressed modified files: {comp_count}")
print(f"Raw (uncompressed) modified files: {raw_count}")

# Critical check: the modified .bin files are DECOMPRESSED versions
# If we put them directly into the CPK, the FileSize in ITOC will be wrong
# Let's compare: modified file size vs original extract size
print(f"\nComparing modified file sizes with original extract sizes:")
size_match = 0
size_differ = 0
for fid in sorted(modified_ids):
    entry = id_to_entry.get(fid)
    if not entry: continue
    mod_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
    if not os.path.exists(mod_path): continue
    mod_size = os.path.getsize(mod_path)
    ext_path = os.path.join(EXTRACTED_DIR, f"ID{fid:05d}.bin")
    ext_size = os.path.getsize(ext_path) if os.path.exists(ext_path) else 0
    
    if mod_size == ext_size:
        size_match += 1
    else:
        size_differ += 1
        if size_differ <= 5:
            print(f"  ID{fid:05d}: extracted={ext_size}, modified={mod_size}, diff={mod_size-ext_size:+d}")

print(f"\n  Same size as extracted: {size_match}")
print(f"  Different from extracted: {size_differ}")

# Check: are the .cache files the compressed versions?
cache_count = 0
for fname in os.listdir(MODIFIED_DIR):
    if '.cache' in fname:
        cache_count += 1
print(f"\n  Cache files (compressed) in modified_cpk: {cache_count}")

os.remove(cpk_temp)

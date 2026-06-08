#!/usr/bin/env python3
"""
Check if recompressed English files (.cache) fit within original sizes.
"""
import struct
import sys
import os
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"

with open(ORIG_ROM, 'rb') as f:
    rom = f.read()

fat_off = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start = struct.unpack_from('<I', rom, fat_off)[0]
cpk_end = struct.unpack_from('<I', rom, fat_off + 4)[0]
orig_cpk = rom[cpk_start:cpk_end]

cpk_temp = "/tmp/sigma_fit_check.cpk"
with open(cpk_temp, 'wb') as f:
    f.write(orig_cpk)
cpk_obj = cpk_module.readCPK(cpk_temp)

id_to_entry = {e.id: e for e in cpk_obj.filetable if e.filetype == "FILE"}

modified_ids = set()
for fname in os.listdir(MODIFIED_DIR):
    if fname.endswith('.bin'):
        try:
            modified_ids.add(int(fname.replace('ID','').replace('.bin','')))
        except: pass

can_fit = 0
cannot_fit = 0

print(f"File ID | Orig FileSize | Orig ExtractSize | Mod Raw Size | Mod Comp Size | Fits?")
print("-" * 85)

for fid in sorted(modified_ids):
    entry = id_to_entry.get(fid)
    if not entry: continue
    
    mod_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
    raw_size = os.path.getsize(mod_path)
    
    # Find .cache file
    comp_size = None
    for fname in os.listdir(MODIFIED_DIR):
        if fname.startswith(f"ID{fid:05d}.bin") and fname.endswith('.cache'):
            comp_size = os.path.getsize(os.path.join(MODIFIED_DIR, fname))
            break
            
    if comp_size is None:
        comp_size = raw_size # Uncompressed
        
    fits = comp_size <= entry.filesize
    if fits: can_fit += 1
    else: cannot_fit += 1
    
    if not fits:
        print(f"  {fid:5d} | {entry.filesize:13,} | {entry.extractsize:16,} | {raw_size:12,} | {comp_size:13,} | NO (+{comp_size - entry.filesize})")

print("-" * 85)
print(f"Total modified files: {len(modified_ids)}")
print(f"Can fit: {can_fit}")
print(f"Cannot fit: {cannot_fit}")

os.remove(cpk_temp)

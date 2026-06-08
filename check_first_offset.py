#!/usr/bin/env python3
"""
Diagnostic: check which offsets changed.
"""
import sys
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_CPK = "/tmp/orig.cpk"
PAD_CPK = "/tmp/pad.cpk"

if not os.path.exists(ORIG_CPK) or not os.path.exists(PAD_CPK):
    # Need to extract them again
    import struct
    orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
    pad_rom = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"
    with open(orig_rom, 'rb') as f: orig = f.read()
    with open(pad_rom, 'rb') as f: pad = f.read()
    
    fat_off = struct.unpack_from('<I', orig, 0x48)[0]
    c_start = struct.unpack_from('<I', orig, fat_off)[0]
    c_end = struct.unpack_from('<I', orig, fat_off+4)[0]
    
    with open(ORIG_CPK, 'wb') as f: f.write(orig[c_start:c_end])
    with open(PAD_CPK, 'wb') as f: f.write(pad[c_start:c_end])

cpk_orig = cpk_module.readCPK(ORIG_CPK)
cpk_pad = cpk_module.readCPK(PAD_CPK)

eo = sorted([e for e in cpk_orig.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)
ep = sorted([e for e in cpk_pad.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

first_changed_id = None
first_changed_idx = None

for i in range(len(eo)):
    if eo[i].fileoffset != ep[i].fileoffset:
        first_changed_id = eo[i].id
        first_changed_idx = i
        break

print(f"First changed offset is at file index {first_changed_idx}, ID {first_changed_id}")
print(f"Original offset: {eo[first_changed_idx].fileoffset}")
print(f"Padded offset: {ep[first_changed_idx].fileoffset}")

# Let's see if any files BEFORE this index have hardcoded checks?
# If the first changed offset is ID 4026 (index 4026), then files 0-4025 are EXACTLY the same!

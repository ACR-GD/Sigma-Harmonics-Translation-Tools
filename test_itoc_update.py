#!/usr/bin/env python3
"""
Test if hacktools repack correctly updates the ITOC rawpacket.
"""
import struct
import sys
import os
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
EXTRACTED_DIR = "/Users/acr/Develop/sigma-harmonics/extracted_cpk/"
MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"

with open(ORIG_ROM, 'rb') as f:
    rom = f.read()

fat_off = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start = struct.unpack_from('<I', rom, fat_off)[0]
cpk_end = struct.unpack_from('<I', rom, fat_off + 4)[0]
orig_cpk = rom[cpk_start:cpk_end]

cpk_temp = "/tmp/sigma_test_itoc.cpk"
with open(cpk_temp, 'wb') as f:
    f.write(orig_cpk)

cpk_obj = cpk_module.readCPK(cpk_temp)
repacked_path = "/tmp/sigma_test_repacked.cpk"

print("Repacking...")
cpk_module.repack(cpk_temp, repacked_path, EXTRACTED_DIR, MODIFIED_DIR)

# Check the ITOC entry
itoc_entry = cpk_obj.getFileEntry("ITOC_HDR")
if itoc_entry:
    itoc_entry.utf.rawpacket.seek(0)
    new_utf = itoc_entry.utf.rawpacket.read()
    print(f"New UTF size: {len(new_utf)}")
    print(f"Starts with @UTF: {new_utf[:4] == b'@UTF'}")
    
    itoc_pos = orig_cpk.find(b'ITOC')
    orig_itoc = orig_cpk[itoc_pos:]
    orig_utf = orig_itoc[16:]
    print(f"Orig UTF size: {len(orig_utf)}")
    print(f"Sizes match: {len(new_utf) == len(orig_utf)}")
    
    # Check if they differ (they should, due to size updates)
    if new_utf != orig_utf:
        print("UTF tables differ (expected).")
    else:
        print("WARNING: UTF tables are identical!")

os.remove(cpk_temp)
os.remove(repacked_path)

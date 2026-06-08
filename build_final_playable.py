#!/usr/bin/env python3
import sys
import struct
import os
import glob

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
test_rom = "/Users/acr/Develop/sigma-harmonics/sigma_en_playable.nds"
mod_cpk_dir = "/Users/acr/Develop/sigma-harmonics/modified_cpk"

with open(orig_rom, 'rb') as f:
    rom = bytearray(f.read())
    
fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start, cpk_end = struct.unpack_from('<II', rom, fat_offset)

orig_cpk = bytearray(rom[cpk_start:cpk_end])
cpk_temp = "/tmp/orig.cpk"
with open(cpk_temp, 'wb') as f: f.write(orig_cpk)

c = cpk_module.readCPK(cpk_temp)
file_entries = sorted([e for e in c.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

replaced_count = 0
reverted_count = 0

for e in file_entries:
    filename = f"ID{e.id:05d}.bin"
    cache_files = glob.glob(os.path.join(mod_cpk_dir, f"{filename}_*.cache"))
    if cache_files:
        cache_path = cache_files[0]
        with open(cache_path, 'rb') as f:
            comp = bytearray(f.read())
            
        # STRIP CRILAYLA SIGNATURE
        if comp[:8] == b"CRILAYLA":
            comp[:8] = b"\x00" * 8
            
        if len(comp) > e.filesize:
            # DOES NOT FIT. REVERT TO JAPANESE TO PREVENT CRASH/FREEZE.
            comp = orig_cpk[e.fileoffset:e.fileoffset+e.filesize]
            reverted_count += 1
            print(f"Reverted {filename} to Japanese (needs {len(comp)} bytes, but slot is {e.filesize} bytes)")
        elif len(comp) <= e.filesize:
            # PAD WITH ZEROS
            comp += b'\x00' * (e.filesize - len(comp))
            replaced_count += 1
            
        orig_cpk[e.fileoffset:e.fileoffset+e.filesize] = comp

print(f"Successfully translated {replaced_count} files.")
print(f"Reverted {reverted_count} files to Japanese because they exceeded their physical slot size.")

rom[cpk_start:cpk_end] = orig_cpk
with open(test_rom, 'wb') as f:
    f.write(rom)

print(f"Created {test_rom}")

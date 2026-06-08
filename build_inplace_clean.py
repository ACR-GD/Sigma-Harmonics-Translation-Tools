#!/usr/bin/env python3
import sys
import struct
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
test_rom = "/Users/acr/Develop/sigma-harmonics/sigma_en_inplace.nds"
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

# Replace files in place
import hacktools.cmp_cri as cmp_cri

replaced_count = 0
truncated_count = 0

for e in file_entries:
    filename = f"ID{e.id:05d}.bin"
    mod_path = os.path.join(mod_cpk_dir, filename)
    if os.path.exists(mod_path):
        with open(mod_path, 'rb') as f:
            new_data = f.read()
            
        # Re-compress
        print(f"Compressing {filename}..."); sys.stdout.flush(); comp = cmp_cri.compressCRILAYLA(new_data)
        
        # Check size
        if len(comp) > e.filesize:
            # Truncate!
            comp = comp[:e.filesize]
            truncated_count += 1
            print(f"Truncated {filename} to {e.filesize} bytes (was {len(comp)})")
        elif len(comp) < e.filesize:
            # Pad with zeros
            comp += b'\x00' * (e.filesize - len(comp))
            
        orig_cpk[e.fileoffset:e.fileoffset+e.filesize] = comp
        replaced_count += 1

print(f"Replaced {replaced_count} files, truncated {truncated_count} files.")

rom[cpk_start:cpk_end] = orig_cpk
with open(test_rom, 'wb') as f:
    f.write(rom)

print(f"Created {test_rom}")

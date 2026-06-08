#!/usr/bin/env python3
import os

MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"
EXTRACTED_DIR = "/Users/acr/Develop/sigma-harmonics/extracted_cpk/"

for fid in [4030, 4198]:
    mod_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
    ext_path = os.path.join(EXTRACTED_DIR, f"ID{fid:05d}.bin")
    
    if os.path.exists(mod_path) and os.path.exists(ext_path):
        mod_size = os.path.getsize(mod_path)
        ext_size = os.path.getsize(ext_path)
        print(f"\nID {fid}: Extracted = {ext_size} bytes, Modified = {mod_size} bytes")
        
        with open(ext_path, 'rb') as f:
            ext_data = f.read()
        with open(mod_path, 'rb') as f:
            mod_data = f.read()
            
        print(f"Extracted Header: {ext_data[:32].hex()}")
        print(f"Modified Header:  {mod_data[:32].hex()}")
        
        diff_len = mod_size - ext_size
        if diff_len > 0:
            extra_data = mod_data[ext_size:ext_size+64]
            print(f"First 64 bytes of appended data: {extra_data.hex()}")
            zero_count = mod_data[ext_size:].count(b'\x00')
            print(f"Zeros in appended data: {zero_count} out of {diff_len}")

#!/usr/bin/env python3
"""
Diagnostic: Compare v6 (in-place) and padded (rebuilder) ITOC changes.
"""
import sys
import struct
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
V6_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en_v6.nds"  # Let's rebuild a V6 temporarily
PADDED_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds" # currently padded

# Rebuild a v6 rom to compare
# ... actually I can just analyze the PADDED_ROM to see what changed in the ITOC compared to original

with open(ORIG_ROM, 'rb') as f:
    orig = f.read()
with open(PADDED_ROM, 'rb') as f:
    padded = f.read()
    
fat_off = struct.unpack_from('<I', orig, 0x48)[0]
cpk_start = struct.unpack_from('<I', orig, fat_off)[0]

orig_cpk = orig[cpk_start:]
padded_cpk = padded[cpk_start:]

itoc_pos = orig_cpk.find(b'ITOC')
orig_itoc = orig_cpk[itoc_pos:]
padded_itoc = padded_cpk[itoc_pos:]

print(f"Orig ITOC pos: {itoc_pos}")
if orig_itoc[:4] != b'ITOC' or padded_itoc[:4] != b'ITOC':
    print("ITOC missing!")
    sys.exit()

diffs = 0
for i in range(min(len(orig_itoc), len(padded_itoc))):
    if orig_itoc[i] != padded_itoc[i]:
        diffs += 1
        
print(f"ITOC differences: {diffs} bytes")

# Parse both ITOCs
with open("/tmp/orig.cpk", 'wb') as f: f.write(orig_cpk)
with open("/tmp/pad.cpk", 'wb') as f: f.write(padded_cpk)

cpk_orig = cpk_module.readCPK("/tmp/orig.cpk")
cpk_pad = cpk_module.readCPK("/tmp/pad.cpk")

# Check FileSize of all files
file_entries_orig = sorted([e for e in cpk_orig.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)
file_entries_pad = sorted([e for e in cpk_pad.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

changed_filesize = 0
changed_extractsize = 0
changed_offsets = 0

for i in range(len(file_entries_orig)):
    eo = file_entries_orig[i]
    ep = file_entries_pad[i]
    
    if eo.filesize != ep.filesize:
        changed_filesize += 1
    if eo.extractsize != ep.extractsize:
        changed_extractsize += 1
    if eo.fileoffset != ep.fileoffset:
        changed_offsets += 1

print(f"Files with changed FileSize: {changed_filesize}")
print(f"Files with changed ExtractSize: {changed_extractsize}")
print(f"Files with changed calculated offset: {changed_offsets}")

os.remove("/tmp/orig.cpk")
os.remove("/tmp/pad.cpk")

#!/usr/bin/env python3
"""
Check adjacent files for the 22 overflowing files to see if we can steal space.
"""
import sys
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

ORIG_CPK = "/tmp/orig.cpk"

cpk_obj = cpk_module.readCPK(ORIG_CPK)
file_entries = sorted([e for e in cpk_obj.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

overflowing_ids = [4030, 4031, 4085, 4087, 4093, 4135, 4175, 4198, 4203, 4215, 4219, 4221, 4237, 4261, 4263, 4275, 4321, 4406, 4511, 4846, 4887, 5025]

def get_entry_by_id(fid):
    for i, e in enumerate(file_entries):
        if e.id == fid:
            return i, e
    return None, None

print(f"{'ID':<6} {'Orig Size':<10} {'Next ID':<8} {'Next Size':<10} {'Next Type':<10}")
print("-" * 50)
for fid in overflowing_ids:
    idx, entry = get_entry_by_id(fid)
    if idx is not None and idx + 1 < len(file_entries):
        next_entry = file_entries[idx+1]
        print(f"{fid:<6} {entry.filesize:<10} {next_entry.id:<8} {next_entry.filesize:<10}")

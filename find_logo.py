#!/usr/bin/env python3
"""
Find logo files in the CPK by looking at headers of early files.
"""
import sys
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_cpk = "/tmp/orig.cpk"
with open(orig_cpk, 'rb') as f:
    data = f.read()
    
cpk_obj = cpk_module.readCPK(orig_cpk)

for e in sorted([e for e in cpk_obj.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)[:100]:
    f_data = data[e.fileoffset:e.fileoffset+e.filesize]
    header = f_data[:8].hex()
    print(f"ID {e.id:5d} Offset {e.fileoffset:8X} Size {e.filesize:8d} Header {header}")

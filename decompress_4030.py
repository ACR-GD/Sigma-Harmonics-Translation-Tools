#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module, cmp_cri

cpk_temp = "/tmp/orig.cpk"
cpk_obj = cpk_module.readCPK(cpk_temp)
e = cpk_obj.getIDEntry(4030)

with open(cpk_temp, 'rb') as f:
    f.seek(e.fileoffset)
    data = bytearray(f.read(e.filesize))
    
if data[:8] == b'\x00'*8:
    data[:8] = b'CRILAYLA'
    dec = cmp_cri.decompressCRILAYLA(bytes(data))
    print(f"Decompressed to {len(dec)} bytes. (Expected: {e.extractsize})")
    print(f"Header: {dec[:32].hex()}")

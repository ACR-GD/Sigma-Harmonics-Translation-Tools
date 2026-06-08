#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

cpk_temp = "/tmp/orig.cpk"
cpk_obj = cpk_module.readCPK(cpk_temp)

e = cpk_obj.getIDEntry(4030)
print(f"ID 4030: Offset={e.fileoffset}, Size={e.filesize}, ExtractSize={e.extractsize}")

with open(cpk_temp, 'rb') as f:
    f.seek(e.fileoffset)
    data = f.read(e.filesize)
    print(f"Read {len(data)} bytes")
    
import hacktools.cmp_cri as cmp_cri
if len(data) >= 8 and data[:8] == b'\x00'*8:
    try:
        dec = cmp_cri.decompressCRILAYLA(data)
        print(f"Decompressed successfully: {len(dec)} bytes")
    except Exception as ex:
        print(f"Decompress failed: {ex}")

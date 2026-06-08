#!/usr/bin/env python3
import sys
import multiprocessing

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk, cmp_cri

def safe_decompress(data):
    # Just decompress without multiprocessing to avoid deadlocks!
    try:
        return cmp_cri.decompressCRILAYLA(data)
    except Exception as e:
        print("Decompress error:", e)
        return None

if __name__ == '__main__':
    c = cpk.readCPK('/tmp/orig.cpk')
    e = c.getIDEntry(4025)
    
    with open('/tmp/orig.cpk', 'rb') as f:
        f.seek(e.fileoffset)
        data = bytearray(f.read(e.filesize))
        
    data[:8] = b'CRILAYLA'
    dec = safe_decompress(bytes(data))
    if dec:
        print(f"ID 4025 decompressed to {len(dec)} bytes.")
        with open("/tmp/ID04025_clean.bin", "wb") as f:
            f.write(dec)

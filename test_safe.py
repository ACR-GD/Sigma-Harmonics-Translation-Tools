#!/usr/bin/env python3
import sys
import multiprocessing
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk, cmp_cri

def _decompress_worker(data, conn):
    try:
        dec = cmp_cri.decompressCRILAYLA(data)
        conn.send((True, dec))
    except Exception as e:
        conn.send((False, str(e)))
    finally:
        conn.close()

def safe_decompress(data):
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=_decompress_worker, args=(data, child_conn))
    p.start()
    p.join(timeout=2.0)
    
    if p.is_alive():
        p.terminate()
        p.join()
        print("Timeout!")
        return None
        
    if p.exitcode != 0:
        print(f"Exitcode: {p.exitcode}")
        return None
        
    try:
        success, result = parent_conn.recv()
        if success:
            return result
        else:
            print("Worker error:", result)
    except Exception as e:
        print("Recv error:", e)
    return None

if __name__ == '__main__':
    c = cpk.readCPK('/tmp/orig.cpk')
    e = c.getIDEntry(4030)
    with open('/tmp/orig.cpk', 'rb') as f:
        f.seek(e.fileoffset)
        data = bytearray(f.read(e.filesize))
        
    data[:8] = b'CRILAYLA'
    dec = safe_decompress(bytes(data))
    if dec:
        print(f"Success! {len(dec)} bytes")

#!/usr/bin/env python3
import sys
import os
from hacktools import cpk, common, cmp_cri

import multiprocessing

def _decompress_worker(data, conn):
    try:
        from hacktools import cmp_cri
        dec = cmp_cri.decompressCRILAYLA(data)
        conn.send((True, dec))
    except Exception as e:
        conn.send((False, str(e)))
    finally:
        conn.close()

def safe_decompress_crilayla(data):
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=_decompress_worker, args=(data, child_conn))
    p.start()
    p.join(timeout=2.0)
    
    if p.is_alive():
        p.terminate()
        p.join()
        return None
        
    if p.exitcode != 0:
        return None
        
    try:
        success, result = parent_conn.recv()
        if success:
            return result
    except:
        pass
    return None

def unpack_cpk(cpk_path, output_dir):
    print(f"Extracting CPK archive: {cpk_path} to {output_dir}")
    if not os.path.exists(cpk_path):
        print(f"Error: CPK file not found: {cpk_path}")
        return

    # Enable debug logging from hacktools to see progress
    common.log_level = 1 # LOG_DEBUG
    
    # We define a custom guess extension function to help identify file types
    def guess_extension(data, entry, filename):
        ext = ".bin" # default
        if len(data) >= 4:
            magic = data[:4]
            if magic == b'\x89PNG':
                ext = ".png"
            elif magic == b'GIF8':
                ext = ".gif"
            elif magic == b'BM':
                ext = ".bmp"
            elif magic == b'RIFF' and len(data) >= 12 and data[8:12] == b'WAVE':
                ext = ".wav"
            elif magic == b'SDAT':
                ext = ".sdat"
            elif magic.startswith(b'SARC'):
                ext = ".sarc"
            elif magic.startswith(b'NARC'):
                ext = ".narc"
            elif magic.startswith(b'BMG'):
                ext = ".bmg"
            elif magic.startswith(b'TXTR'):
                ext = ".txtr"
            elif magic.startswith(b'BTI'):
                ext = ".bti"
            elif magic.startswith(b'CRILAYLA'):
                ext = ".layla"
            elif magic.startswith(b'CSB'):
                ext = ".csb"
        
        return filename + ext

    try:
        archive = cpk.readCPK(cpk_path)
        file_entries = [e for e in archive.filetable if e.filetype == "FILE"]
        print(f"Found {len(file_entries)} file entries in CPK. Starting extraction...")
        
        extracted_count = 0
        with open(cpk_path, 'rb') as f:
            for entry in file_entries:
                folder, filename = entry.getFolderFile(output_dir)
                f.seek(entry.fileoffset)
                data = bytearray(f.read(entry.filesize))
                
                # Check for zeroed CRILAYLA header
                if len(data) >= 16 and data[0:8] == b'\x00\x00\x00\x00\x00\x00\x00\x00':
                    # Restore signature and decompress
                    data_mod = bytearray(data)
                    data_mod[0:8] = b"CRILAYLA"
                    dec = safe_decompress_crilayla(bytes(data_mod))
                    if dec is not None:
                        data = dec
                    else:
                        print(f"Warning: Decompression failed/crashed for entry {entry.id}. Using raw bytes.")
                
                # Guess extension
                filename = guess_extension(data, entry, filename)
                os.makedirs(folder, exist_ok=True)
                
                out_path = os.path.join(folder, filename)
                with open(out_path, 'wb') as out_f:
                    out_f.write(data)
                
                extracted_count += 1
                if extracted_count % 500 == 0:
                    print(f"Extracted {extracted_count}/{len(file_entries)} files...")
                    
        print(f"CPK extraction completed successfully. Extracted {extracted_count} files.")
    except Exception as e:
        print("Error extracting CPK:", e)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cpk_unpack.py <cpk_path> <output_dir>")
        sys.exit(1)
        
    unpack_cpk(sys.argv[1], sys.argv[2])

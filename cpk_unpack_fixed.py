#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk, common, cmp_cri

def unpack_cpk(cpk_path, output_dir):
    print(f"Extracting CPK archive: {cpk_path} to {output_dir}")
    if not os.path.exists(cpk_path):
        print(f"Error: CPK file not found: {cpk_path}")
        return

    common.log_level = 1
    
    def guess_extension(data, entry, filename):
        ext = ".bin"
        if len(data) >= 4:
            magic = data[:4]
            if magic == b'\x89PNG': ext = ".png"
            elif magic == b'GIF8': ext = ".gif"
            elif magic == b'BM': ext = ".bmp"
            elif magic == b'RIFF' and len(data) >= 12 and data[8:12] == b'WAVE': ext = ".wav"
            elif magic == b'SDAT': ext = ".sdat"
            elif magic.startswith(b'SARC'): ext = ".sarc"
            elif magic.startswith(b'NARC'): ext = ".narc"
            elif magic.startswith(b'BMG'): ext = ".bmg"
            elif magic.startswith(b'TXTR'): ext = ".txtr"
            elif magic.startswith(b'BTI'): ext = ".bti"
            elif magic.startswith(b'CRILAYLA'): ext = ".layla"
            elif magic.startswith(b'CSB'): ext = ".csb"
        return filename + ext

    archive = cpk.readCPK(cpk_path)
    file_entries = [e for e in archive.filetable if e.filetype == "FILE"]
    print(f"Found {len(file_entries)} file entries. Starting extraction...")
    
    extracted_count = 0
    with open(cpk_path, 'rb') as f:
        for entry in file_entries:
            folder, filename = entry.getFolderFile(output_dir)
            f.seek(entry.fileoffset)
            data = bytearray(f.read(entry.filesize))
            
            if len(data) >= 16 and data[0:8] == b'\x00\x00\x00\x00\x00\x00\x00\x00':
                data_mod = bytearray(data)
                data_mod[0:8] = b"CRILAYLA"
                try:
                    # Decompress synchronously. No deadlock.
                    dec = cmp_cri.decompressCRILAYLA(bytes(data_mod))
                    data = dec
                except Exception as e:
                    print(f"Warning: Decompression failed for entry {entry.id}: {e}")
            
            filename = guess_extension(data, entry, filename)
            os.makedirs(folder, exist_ok=True)
            
            out_path = os.path.join(folder, filename)
            with open(out_path, 'wb') as out_f:
                out_f.write(data)
            
            extracted_count += 1
            if extracted_count % 500 == 0:
                print(f"Extracted {extracted_count}/{len(file_entries)} files...")
                
    print(f"CPK extraction completed successfully. Extracted {extracted_count} files.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cpk_unpack_fixed.py <cpk_path> <output_dir>")
        sys.exit(1)
    unpack_cpk(sys.argv[1], sys.argv[2])

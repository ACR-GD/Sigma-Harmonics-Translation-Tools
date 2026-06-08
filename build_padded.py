#!/usr/bin/env python3
"""
Sigma Harmonics CPK Padded Rebuilder
====================================
Hypothesis: The game has a hardcoded pointer to the ITOC at 0x73D4000 or expects 
the ROM size / FAT to be exactly original. The definitive rebuilder changed 
those offsets, causing a white screen on boot.

This script rebuilds the CPK with correctly compressed English files, updates 
the ITOC file sizes, but then PADS the remaining space so that the ITOC sits 
EXACTLY at 0x73D4000, ensuring all FAT entries and ROM size remain 100% original.
"""
import struct
import sys
import os
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module, common, cmp_cri

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
OUTPUT_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"
MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"

def main():
    print("=" * 60)
    print("Sigma Harmonics Padded CPK Rebuilder")
    print("=" * 60)
    
    with open(ORIG_ROM, 'rb') as f:
        rom = bytearray(f.read())
    
    fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
    cpk_rom_start, cpk_rom_end = struct.unpack_from('<II', rom, fat_offset)
    orig_cpk = bytes(rom[cpk_rom_start:cpk_rom_end])
    
    cpk_temp = "/tmp/sigma_pad_orig.cpk"
    with open(cpk_temp, 'wb') as f:
        f.write(orig_cpk)
    
    cpk_obj = cpk_module.readCPK(cpk_temp)
    align_val = cpk_obj.align
    content_offset = 2048
    itoc_pos = orig_cpk.find(b'ITOC')
    
    file_entries = sorted([e for e in cpk_obj.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)
    
    modified_ids = set()
    for fname in os.listdir(MODIFIED_DIR):
        if fname.endswith('.bin'):
            try: modified_ids.add(int(fname.replace('ID','').replace('.bin','')))
            except: pass
    
    modified_data = {}
    for fid in modified_ids:
        entry = cpk_obj.getIDEntry(fid)
        if not entry: continue
        raw_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
        cache_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin_{common.crcFile(raw_path)}.cache")
        with open(raw_path, 'rb') as f: raw_data = f.read()
        
        if entry.filesize != entry.extractsize:
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f: comp_data = f.read()
            else:
                comp_data = cmp_cri.compressCRILAYLA(raw_data)
            modified_data[fid] = (comp_data, len(raw_data))
        else:
            modified_data[fid] = (raw_data, len(raw_data))
            
    print("Building new content...")
    new_content = bytearray(orig_cpk[:content_offset])
    new_sizes = {}
    
    for i, entry in enumerate(file_entries):
        fid = entry.id
        if fid in modified_data:
            file_data, extract_size = modified_data[fid]
            new_sizes[fid] = (len(file_data), extract_size)
        else:
            local_off = entry.fileoffset
            file_data = orig_cpk[local_off:local_off+entry.filesize]
            new_sizes[fid] = (entry.filesize, entry.extractsize)
        
        new_content.extend(file_data)
        if i + 1 < len(file_entries):
            remainder = len(file_data) % align_val
            if remainder > 0:
                new_content.extend(b'\x00' * (align_val - remainder))
                
    print(f"Content built. Size: {len(new_content):,}")
    print(f"Original ITOC pos:   {itoc_pos:,}")
    
    if len(new_content) > itoc_pos:
        print("ERROR: New content is larger than original ITOC position!")
        print("We cannot use the padded approach.")
        sys.exit(1)
        
    pad_len = itoc_pos - len(new_content)
    print(f"Padding {pad_len:,} bytes to reach ITOC...")
    new_content.extend(b'\xFF' * pad_len)
    
    print("Updating ITOC sizes...")
    orig_itoc_bytes = bytearray(orig_cpk[itoc_pos:])
    itoc_entry = cpk_obj.getFileEntry("ITOC_HDR")
    
    def update_utf(sub_table, offset_in_itoc):
        sub_table.rawpacket.seek(0)
        t_bytes = bytearray(sub_table.rawpacket.read())
        for i in range(sub_table.numrows):
            fid = sub_table.getColumnDataType(i, "ID")[0]
            if fid in new_sizes:
                n_fs, n_es = new_sizes[fid]
                fs_p = sub_table.rows[i][sub_table.columnlookup["FileSize"]].position
                es_p = sub_table.rows[i][sub_table.columnlookup["ExtractSize"]].position
                fs_t = sub_table.rows[i][sub_table.columnlookup["FileSize"]].type
                es_t = sub_table.rows[i][sub_table.columnlookup["ExtractSize"]].type
                
                if fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', t_bytes, fs_p, n_fs)
                elif fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT16: struct.pack_into('>H', t_bytes, fs_p, n_fs)
                if es_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', t_bytes, es_p, n_es)
                elif es_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT16: struct.pack_into('>H', t_bytes, es_p, n_es)
        orig_itoc_bytes[offset_in_itoc:offset_in_itoc+len(t_bytes)] = t_bytes

    if itoc_entry.utf.utfdatah:
        itoc_entry.utf.rawpacket.seek(itoc_entry.utf.datahpos)
        datah_abs = itoc_entry.utf.rawpacket.readInt() + itoc_entry.utf.dataoffset
        update_utf(itoc_entry.utf.utfdatah, 16 + datah_abs)
    if itoc_entry.utf.utfdatal:
        itoc_entry.utf.rawpacket.seek(itoc_entry.utf.datalpos)
        datal_abs = itoc_entry.utf.rawpacket.readInt() + itoc_entry.utf.dataoffset
        update_utf(itoc_entry.utf.utfdatal, 16 + datal_abs)
        
    new_content.extend(orig_itoc_bytes)
    
    print("Patching ROM...")
    rom[cpk_rom_start:cpk_rom_start+len(new_content)] = new_content
    
    with open(OUTPUT_ROM, 'wb') as f:
        f.write(rom)
        
    os.remove(cpk_temp)
    print(f"DONE! ITOC is back at 0x{itoc_pos:X}. ROM size is unchanged.")

if __name__ == '__main__':
    main()

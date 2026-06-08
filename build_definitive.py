#!/usr/bin/env python3
"""
Sigma Harmonics CPK Rebuilder - The Definitive Solution
=======================================================
Since English text is significantly larger than Japanese (e.g. 25KB vs 700 bytes),
in-place patching is physically impossible. We MUST shift file offsets.
To shift offsets, we must properly rebuild the CPK and ITOC.

This script:
1. Re-compresses modified files to save space (using hacktools CRILAYLA).
2. Builds a new CPK file data section sequentially.
3. Uses the hacktools ITOC parsed positions to carefully update
   FileSize and ExtractSize in the DataH/DataL tables.
4. Appends the fixed ITOC to the new CPK.
5. Injects the new CPK into the ROM, shifting the SDAT appropriately.
"""
import struct
import sys
import os
sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module, common, cmp_cri

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
OUTPUT_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"
MODIFIED_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk/"

def align_up(val, alignment):
    return (val + alignment - 1) & ~(alignment - 1)

def main():
    print("=" * 60)
    print("Sigma Harmonics Definitive CPK Rebuilder")
    print("=" * 60)
    
    # 1. Read original ROM
    with open(ORIG_ROM, 'rb') as f:
        rom = bytearray(f.read())
    rom_size = len(rom)
    
    fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
    cpk_rom_start, cpk_rom_end = struct.unpack_from('<II', rom, fat_offset)
    sdat_rom_start, sdat_rom_end = struct.unpack_from('<II', rom, fat_offset + 8)
    
    orig_cpk = bytes(rom[cpk_rom_start:cpk_rom_end])
    sdat_data = bytes(rom[sdat_rom_start:sdat_rom_end])
    
    # 2. Parse original CPK
    cpk_temp = "/tmp/sigma_def_orig.cpk"
    with open(cpk_temp, 'wb') as f:
        f.write(orig_cpk)
    
    cpk_obj = cpk_module.readCPK(cpk_temp)
    align_val = cpk_obj.align
    content_offset = cpk_obj.getFileEntry("CONTENT_OFFSET").fileoffset
    
    file_entries = sorted(
        [e for e in cpk_obj.filetable if e.filetype == "FILE"],
        key=lambda e: e.fileoffset
    )
    
    print(f"CPK: {len(file_entries)} files, align={align_val}, content_offset={content_offset}")
    
    # 3. Load modified files
    modified_ids = set()
    for fname in os.listdir(MODIFIED_DIR):
        if fname.endswith('.bin'):
            try:
                modified_ids.add(int(fname.replace('ID','').replace('.bin','')))
            except: pass
    
    # Compress modified files if they aren't already
    print(f"Loading {len(modified_ids)} modified files...")
    modified_data = {} # id -> (compressed_bytes, extracted_size)
    
    for fid in modified_ids:
        entry = cpk_obj.getIDEntry(fid)
        if not entry: continue
        
        raw_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin")
        cache_path = os.path.join(MODIFIED_DIR, f"ID{fid:05d}.bin_{common.crcFile(raw_path)}.cache")
        
        with open(raw_path, 'rb') as f:
            raw_data = f.read()
        
        # If the original was compressed, compress the new one
        if entry.filesize != entry.extractsize:
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    comp_data = f.read()
            else:
                comp_data = cmp_cri.compressCRILAYLA(raw_data)
                with open(cache_path, 'wb') as f:
                    f.write(comp_data)
            modified_data[fid] = (comp_data, len(raw_data))
        else:
            # Original was not compressed
            modified_data[fid] = (raw_data, len(raw_data))
    
    # 4. Build new CPK file data
    print("Building new CPK content...")
    new_content = bytearray(orig_cpk[:content_offset]) # Header
    
    # We need to track actual sizes for the ITOC update
    new_sizes = {} # id -> (filesize, extractsize)
    
    for i, entry in enumerate(file_entries):
        fid = entry.id
        if fid in modified_data:
            file_data, extract_size = modified_data[fid]
            new_sizes[fid] = (len(file_data), extract_size)
        else:
            # Original data
            local_off = entry.fileoffset
            file_data = orig_cpk[local_off:local_off+entry.filesize]
            new_sizes[fid] = (entry.filesize, entry.extractsize)
        
        new_content.extend(file_data)
        
        # Align
        if i + 1 < len(file_entries):
            remainder = len(file_data) % align_val
            if remainder > 0:
                new_content.extend(b'\x00' * (align_val - remainder))
    
    # 5. Update ITOC
    print("Updating ITOC...")
    itoc_pos = orig_cpk.find(b'ITOC')
    orig_itoc_bytes = bytearray(orig_cpk[itoc_pos:])
    
    itoc_entry = cpk_obj.getFileEntry("ITOC_HDR")
    
    def update_utf_table(sub_table, utf_pos_in_itoc, is_datah):
        # sub_table is e.g. itoc_entry.utf.utfdatah
        sub_table.rawpacket.seek(0)
        table_bytes = bytearray(sub_table.rawpacket.read())
        
        updates = 0
        for i in range(sub_table.numrows):
            fid = sub_table.getColumnDataType(i, "ID")[0]
            if fid in new_sizes:
                new_fs, new_es = new_sizes[fid]
                
                # Get positions inside the rawpacket
                fs_pos = sub_table.rows[i][sub_table.columnlookup["FileSize"]].position
                es_pos = sub_table.rows[i][sub_table.columnlookup["ExtractSize"]].position
                
                fs_type = sub_table.rows[i][sub_table.columnlookup["FileSize"]].type
                es_type = sub_table.rows[i][sub_table.columnlookup["ExtractSize"]].type
                
                # Update in our local bytearray
                if fs_type == cpk_module.UTFStructTypes.DATA_TYPE_UINT32:
                    struct.pack_into('>I', table_bytes, fs_pos, new_fs)
                elif fs_type == cpk_module.UTFStructTypes.DATA_TYPE_UINT16:
                    struct.pack_into('>H', table_bytes, fs_pos, new_fs)
                    
                if es_type == cpk_module.UTFStructTypes.DATA_TYPE_UINT32:
                    struct.pack_into('>I', table_bytes, es_pos, new_es)
                elif es_type == cpk_module.UTFStructTypes.DATA_TYPE_UINT16:
                    struct.pack_into('>H', table_bytes, es_pos, new_es)
                
                if fid in modified_data:
                    updates += 1
        
        # Replace the table in our ITOC copy
        orig_itoc_bytes[utf_pos_in_itoc:utf_pos_in_itoc+len(table_bytes)] = table_bytes
        print(f"  Updated {updates} entries in sub-table")
    
    # Update DataH
    if itoc_entry.utf.utfdatah:
        itoc_entry.utf.rawpacket.seek(itoc_entry.utf.datahpos)
        datah_abs = itoc_entry.utf.rawpacket.readInt() + itoc_entry.utf.dataoffset
        update_utf_table(itoc_entry.utf.utfdatah, 16 + datah_abs, True)
        
    # Update DataL
    if itoc_entry.utf.utfdatal:
        itoc_entry.utf.rawpacket.seek(itoc_entry.utf.datalpos)
        datal_abs = itoc_entry.utf.rawpacket.readInt() + itoc_entry.utf.dataoffset
        update_utf_table(itoc_entry.utf.utfdatal, 16 + datal_abs, False)
    
    # 6. Assemble Final CPK
    new_itoc_pos = len(new_content)
    itoc_align_rem = new_itoc_pos % align_val
    if itoc_align_rem > 0:
        new_content.extend(b'\x00' * (align_val - itoc_align_rem))
        new_itoc_pos = len(new_content)
        
    new_content.extend(orig_itoc_bytes)
    
    # Update ItocOffset in header
    old_itoc_be = struct.pack('>Q', itoc_pos)
    new_itoc_be = struct.pack('>Q', new_itoc_pos)
    idx = new_content.find(old_itoc_be, 0, content_offset)
    if idx >= 0:
        new_content[idx:idx+8] = new_itoc_be
        print(f"Updated ItocOffset to 0x{new_itoc_pos:X}")
    else:
        print("WARNING: ItocOffset not found in header!")
        
    final_cpk = bytes(new_content)
    print(f"Final CPK size: {len(final_cpk):,} (orig: {len(orig_cpk):,})")
    
    # 7. Patch ROM
    print("Patching ROM...")
    new_cpk_end = cpk_rom_start + len(final_cpk)
    new_sdat_start = align_up(new_cpk_end, 0x200)
    new_sdat_end = new_sdat_start + len(sdat_data)
    
    if new_sdat_end > rom_size:
        print("ERROR: ROM overflow!")
        sys.exit(1)
        
    rom[cpk_rom_start:cpk_rom_start+len(final_cpk)] = final_cpk
    
    if new_cpk_end < new_sdat_start:
        rom[new_cpk_end:new_sdat_start] = b'\xFF' * (new_sdat_start - new_cpk_end)
        
    rom[new_sdat_start:new_sdat_end] = sdat_data
    
    if new_sdat_end < rom_size:
        rom[new_sdat_end:rom_size] = b'\xFF' * (rom_size - new_sdat_end)
        
    struct.pack_into('<II', rom, fat_offset, cpk_rom_start, cpk_rom_start + len(final_cpk))
    struct.pack_into('<II', rom, fat_offset + 8, new_sdat_start, new_sdat_end)
    
    # Header CRC
    def crc16(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1: crc = (crc >> 1) ^ 0xA001
                else: crc >>= 1
        return crc & 0xFFFF
    struct.pack_into('<H', rom, 0x15E, crc16(rom[0:0x15E]))
    
    # 8. Write Output
    with open(OUTPUT_ROM, 'wb') as f:
        f.write(rom)
    
    os.remove(cpk_temp)
    print(f"DONE! Wrote {OUTPUT_ROM}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import sys
import os
import glob
import shutil

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk, common, nds

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
out_rom = "/Users/acr/Develop/sigma-harmonics/sigma_en_perfect.nds"
work_dir = "/Users/acr/Develop/sigma-harmonics/rom_work/"
mod_cpk_dir = "/Users/acr/Develop/sigma-harmonics/modified_cpk"

if os.path.exists(work_dir):
    shutil.rmtree(work_dir)
os.makedirs(work_dir)

print("Extracting ROM...")
nds.extractRom(orig_rom, orig_rom.replace('.nds', '.dsdec.nds'), work_dir)

orig_cpk = os.path.join(work_dir, "data", "data.cpk")

# We will modify the CPK repack logic from hacktools to strip signatures
print("Repacking CPK with stripped signatures...")

archive = cpk.readCPK(orig_cpk)
out_cpk = os.path.join(work_dir, "data_repacked.cpk")

with common.Stream(orig_cpk, "rb") as fin:
    with common.Stream(out_cpk, "wb") as fout:
        # Copy header
        fin.seek(0)
        fout.write(fin.read(2048))
        
        file_entries = sorted([e for e in archive.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)
        
        for e in file_entries:
            filename = f"ID{e.id:05d}.bin"
            cache_files = glob.glob(os.path.join(mod_cpk_dir, f"{filename}_*.cache"))
            
            if cache_files:
                with open(cache_files[0], 'rb') as cf:
                    comp = bytearray(cf.read())
                if comp[:8] == b"CRILAYLA":
                    comp[:8] = b"\x00" * 8
            else:
                fin.seek(e.fileoffset)
                comp = fin.read(e.filesize)
                
            e.offset = fout.tell()
            e.filesize = len(comp)
            # DO NOT CHANGE e.extractsize to trick the engine!
            
            fout.write(comp)
            
            # Align
            align = 512
            if fout.tell() % align > 0:
                fout.write(b"\x00" * (align - (fout.tell() % align)))
                
        # Now update ITOC and CPK headers
        content_size = fout.tell() - 2048
        
        itoc_pos = fout.tell()
        itoc_entry = archive.getFileEntry("ITOC_HDR")
        fin.seek(itoc_entry.fileoffset)
        itoc_data = fin.read(itoc_entry.filesize)
        fout.write(itoc_data)
        
        # Update sizes in ITOC
        def update_utf(utf_table, itoc_abs_offset):
            utf_table.rawpacket.seek(0)
            t_bytes = bytearray(utf_table.rawpacket.read())
            import struct
            for i in range(utf_table.numrows):
                fid = utf_table.getColumnDataType(i, "ID")[0]
                matching = next((ent for ent in file_entries if ent.id == fid), None)
                if matching:
                    fs_p = utf_table.rows[i][utf_table.columnlookup["FileSize"]].position
                    fs_t = utf_table.rows[i][utf_table.columnlookup["FileSize"]].type
                    if fs_t == cpk.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', t_bytes, fs_p, matching.filesize)
                    elif fs_t == cpk.UTFStructTypes.DATA_TYPE_UINT16: struct.pack_into('>H', t_bytes, fs_p, matching.filesize)
            fout.seek(itoc_abs_offset)
            fout.write(t_bytes)
            
        if itoc_entry.utf.utfdatah:
            datah_abs = itoc_entry.utf.rawpacket.readInt(itoc_entry.utf.datahpos) + itoc_entry.utf.dataoffset
            update_utf(itoc_entry.utf.utfdatah, itoc_pos + 16 + datah_abs)
        if itoc_entry.utf.utfdatal:
            datal_abs = itoc_entry.utf.rawpacket.readInt(itoc_entry.utf.datalpos) + itoc_entry.utf.dataoffset
            update_utf(itoc_entry.utf.utfdatal, itoc_pos + 16 + datal_abs)
            
        # Update CPK Header
        fout.seek(0)
        cpk_entry = archive.getFileEntry("CPK_HDR")
        fin.seek(0)
        cpk_bytes = bytearray(fin.read(2048))
        import struct
        
        # Update ContentSize
        if cpk_entry.utf.contentsizetype == cpk.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', cpk_bytes, 16 + cpk_entry.utf.contentsizepos, content_size)
        elif cpk_entry.utf.contentsizetype == cpk.UTFStructTypes.DATA_TYPE_UINT64: struct.pack_into('>Q', cpk_bytes, 16 + cpk_entry.utf.contentsizepos, content_size)
        
        # Update ItocOffset
        if cpk_entry.utf.itocoffsettype == cpk.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', cpk_bytes, 16 + cpk_entry.utf.itocoffsetpos, itoc_pos)
        elif cpk_entry.utf.itocoffsettype == cpk.UTFStructTypes.DATA_TYPE_UINT64: struct.pack_into('>Q', cpk_bytes, 16 + cpk_entry.utf.itocoffsetpos, itoc_pos)
        
        fout.seek(0)
        fout.write(cpk_bytes)
        
# Replace data.cpk
shutil.move(out_cpk, orig_cpk)

print("Repacking ROM...")
nds.repackRom(orig_rom, out_rom, work_dir)
print(f"Saved to {out_rom}")

#!/usr/bin/env python3
import sys
import struct
import os
import glob

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
out_cpk = "/Users/acr/Develop/sigma-harmonics/data_new.cpk"
mod_cpk_dir = "/Users/acr/Develop/sigma-harmonics/modified_cpk"

with open(orig_rom, 'rb') as f:
    rom = bytearray(f.read())
    
fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start, cpk_end = struct.unpack_from('<II', rom, fat_offset)
orig_cpk = bytearray(rom[cpk_start:cpk_end])

cpk_temp = "/tmp/orig.cpk"
with open(cpk_temp, 'wb') as f: f.write(orig_cpk)

c = cpk_module.readCPK(cpk_temp)
file_entries = sorted([e for e in c.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

new_content = bytearray(orig_cpk[:2048])
itoc_pos = orig_cpk.find(b'ITOC')
orig_itoc_bytes = bytearray(orig_cpk[itoc_pos:])

for e in file_entries:
    filename = f"ID{e.id:05d}.bin"
    cache_files = glob.glob(os.path.join(mod_cpk_dir, f"{filename}_*.cache"))
    if cache_files:
        with open(cache_files[0], 'rb') as f:
            comp = bytearray(f.read())
        # STRIP CRILAYLA SIGNATURE AND ZERO IT!
        if comp[:8] == b"CRILAYLA":
            comp[:8] = b"\x00" * 8
    else:
        comp = orig_cpk[e.fileoffset:e.fileoffset+e.filesize]
        
    new_content.extend(comp)
    
    if len(comp) != e.filesize:
        e.filesize = len(comp)
        
    remainder = len(new_content) % 512
    if remainder > 0:
        new_content.extend(b'\x00' * (512 - remainder))

# PAD ITOC OFFSET SO ITOC POS DOES NOT CHANGE RELATIVE TO CPK HEADER
itoc_target_offset = itoc_pos
padding_needed = itoc_target_offset - len(new_content)
if padding_needed > 0:
    new_content.extend(b'\x00' * padding_needed)

# Calculate new ContentSize
content_size = len(new_content) - 2048

# Update ITOC table with new FileSizes
itoc_entry = c.getFileEntry("ITOC_HDR")
def update_utf(sub_table, offset_in_itoc):
    sub_table.rawpacket.seek(0)
    t_bytes = bytearray(sub_table.rawpacket.read())
    for i in range(sub_table.numrows):
        fid = sub_table.getColumnDataType(i, "ID")[0]
        matching = next((ent for ent in file_entries if ent.id == fid), None)
        if matching:
            fs_p = sub_table.rows[i][sub_table.columnlookup["FileSize"]].position
            fs_t = sub_table.rows[i][sub_table.columnlookup["FileSize"]].type
            if fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', t_bytes, fs_p, matching.filesize)
            elif fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT16: struct.pack_into('>H', t_bytes, fs_p, matching.filesize)
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

# UPDATE CPK HEADER (ContentSize and ItocOffset)
cpk_entry = c.getFileEntry("CPK_HDR")
if cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ContentSize"]].type == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', new_content, 16 + cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ContentSize"]].position, content_size)
elif cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ContentSize"]].type == cpk_module.UTFStructTypes.DATA_TYPE_UINT64: struct.pack_into('>Q', new_content, 16 + cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ContentSize"]].position, content_size)

new_itoc_pos = len(new_content) - len(orig_itoc_bytes)
if cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ItocOffset"]].type == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', new_content, 16 + cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ItocOffset"]].position, new_itoc_pos)
elif cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ItocOffset"]].type == cpk_module.UTFStructTypes.DATA_TYPE_UINT64: struct.pack_into('>Q', new_content, 16 + cpk_entry.utf.rows[0][cpk_entry.utf.columnlookup["ItocOffset"]].position, new_itoc_pos)

with open(out_cpk, 'wb') as f:
    f.write(new_content)
print(f"Created {out_cpk} (Size: {len(new_content)} bytes)")

#!/usr/bin/env python3
import sys
import struct
import os

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
test_rom = "/Users/acr/Develop/sigma-harmonics/test_shift.nds"

with open(orig_rom, 'rb') as f:
    rom = bytearray(f.read())
    
fat_offset = struct.unpack_from('<I', rom, 0x48)[0]
cpk_start, cpk_end = struct.unpack_from('<II', rom, fat_offset)

orig_cpk = bytes(rom[cpk_start:cpk_end])
cpk_temp = "/tmp/orig.cpk"
with open(cpk_temp, 'wb') as f: f.write(orig_cpk)

c = cpk_module.readCPK(cpk_temp)
file_entries = sorted([e for e in c.filetable if e.filetype == "FILE"], key=lambda e: e.fileoffset)

# We will increase the FileSize of ID 4025 by 512 bytes in the ITOC,
# and insert 512 bytes of zeros into the CPK data.
# This will shift ALL subsequent files by 512 bytes.

new_content = bytearray(orig_cpk[:2048]) # header up to content
for e in file_entries:
    f_data = orig_cpk[e.fileoffset:e.fileoffset+e.filesize]
    new_content.extend(f_data)
    
    if e.id == 4025:
        # Pad this file to shift everything else
        new_content.extend(b'\x00' * 512)
        
    remainder = len(new_content) % 512
    if remainder > 0:
        new_content.extend(b'\x00' * (512 - remainder))

itoc_pos = orig_cpk.find(b'ITOC')
orig_itoc_bytes = bytearray(orig_cpk[itoc_pos:])

itoc_entry = c.getFileEntry("ITOC_HDR")
def update_utf(sub_table, offset_in_itoc):
    sub_table.rawpacket.seek(0)
    t_bytes = bytearray(sub_table.rawpacket.read())
    for i in range(sub_table.numrows):
        fid = sub_table.getColumnDataType(i, "ID")[0]
        if fid == 4025:
            fs_p = sub_table.rows[i][sub_table.columnlookup["FileSize"]].position
            fs_t = sub_table.rows[i][sub_table.columnlookup["FileSize"]].type
            old_fs = sub_table.getColumnDataType(i, "FileSize")[0]
            if fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT32: struct.pack_into('>I', t_bytes, fs_p, old_fs + 512)
            elif fs_t == cpk_module.UTFStructTypes.DATA_TYPE_UINT16: struct.pack_into('>H', t_bytes, fs_p, old_fs + 512)
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

# Pad to keep ITOC offset same? No, let the ITOC shift so we see if shifting ITOC breaks the game.
rom[cpk_start:cpk_end] = new_content
struct.pack_into('<I', rom, fat_offset+4, cpk_start + len(new_content)) # update FAT end

# sound_data.sdat starts right after CPK
sound_start, sound_end = struct.unpack_from('<II', rom, fat_offset + 8)
diff = len(new_content) - len(orig_cpk)
struct.pack_into('<I', rom, fat_offset + 8, sound_start + diff)
struct.pack_into('<I', rom, fat_offset + 12, sound_end + diff)

with open(test_rom, 'wb') as f:
    f.write(rom)

print("Created test_shift.nds")

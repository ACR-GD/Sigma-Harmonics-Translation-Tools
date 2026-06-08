#!/usr/bin/env python3
import sys
import struct
import os
import glob

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk as cpk_module

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
test_rom = "/Users/acr/Develop/sigma-harmonics/sigma_en_padded.nds"
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

# We will build a brand new CPK data section
new_content = bytearray(orig_cpk[:2048])
itoc_pos = orig_cpk.find(b'ITOC')
orig_itoc_bytes = bytearray(orig_cpk[itoc_pos:])

replaced_count = 0

for e in file_entries:
    filename = f"ID{e.id:05d}.bin"
    cache_files = glob.glob(os.path.join(mod_cpk_dir, f"{filename}_*.cache"))
    if cache_files:
        with open(cache_files[0], 'rb') as f:
            comp = bytearray(f.read())
        # STRIP CRILAYLA SIGNATURE AND ZERO IT!
        if comp[:8] == b"CRILAYLA":
            comp[:8] = b"\x00" * 8
        replaced_count += 1
    else:
        # Original file data
        comp = orig_cpk[e.fileoffset:e.fileoffset+e.filesize]
        
    new_content.extend(comp)
    
    # Update ITOC FileSize
    if len(comp) != e.filesize:
        e.filesize = len(comp) # For ITOC update later
        
    remainder = len(new_content) % 512
    if remainder > 0:
        new_content.extend(b'\x00' * (512 - remainder))

# Now we have new_content up to ITOC.
itoc_target_offset = itoc_pos

if len(new_content) > itoc_target_offset:
    print(f"ERROR: new CPK data ({len(new_content)}) exceeds original ITOC offset ({itoc_target_offset}). Cannot pad!")
    sys.exit(1)

# Pad to hit exact original ITOC offset
padding_needed = itoc_target_offset - len(new_content)
if padding_needed > 0:
    new_content.extend(b'\x00' * padding_needed)

# Update ITOC table with new FileSizes
itoc_entry = c.getFileEntry("ITOC_HDR")
def update_utf(sub_table, offset_in_itoc):
    sub_table.rawpacket.seek(0)
    t_bytes = bytearray(sub_table.rawpacket.read())
    for i in range(sub_table.numrows):
        fid = sub_table.getColumnDataType(i, "ID")[0]
        # find matching entry
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

print(f"Replaced {replaced_count} files.")
print(f"Padded {padding_needed} bytes to maintain ITOC at {itoc_target_offset}.")

rom[cpk_start:cpk_end] = new_content
struct.pack_into('<I', rom, fat_offset+4, cpk_start + len(new_content))

sound_start, sound_end = struct.unpack_from('<II', rom, fat_offset + 8)
diff = len(new_content) - len(orig_cpk)
struct.pack_into('<I', rom, fat_offset + 8, sound_start + diff)
struct.pack_into('<I', rom, fat_offset + 12, sound_end + diff)

with open(test_rom, 'wb') as f:
    f.write(rom)

print(f"Created {test_rom}")

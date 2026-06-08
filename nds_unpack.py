#!/usr/bin/env python3
import os
import sys
import struct

def parse_nds(rom_path, out_dir):
    print(f"Reading NDS ROM: {rom_path}")
    if not os.path.exists(rom_path):
        print(f"Error: ROM file not found: {rom_path}")
        return

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # NDS Header parsing
    # Offsets:
    # 0x00: Game Title (12 bytes)
    # 0x0C: Game Code (4 bytes)
    # 0x40: FNT offset (4 bytes)
    # 0x44: FNT size (4 bytes)
    # 0x48: FAT offset (4 bytes)
    # 0x4C: FAT size (4 bytes)
    
    title = rom_data[0:12].decode('ascii', errors='ignore').strip('\x00')
    code = rom_data[12:16].decode('ascii', errors='ignore')
    
    fnt_offset, fnt_size = struct.unpack('<II', rom_data[0x40:0x48])
    fat_offset, fat_size = struct.unpack('<II', rom_data[0x48:0x50])
    
    print(f"Game Title: {title}")
    print(f"Game Code:  {code}")
    print(f"FNT Offset: 0x{fnt_offset:X}, Size: {fnt_size} bytes")
    print(f"FAT Offset: 0x{fat_offset:X}, Size: {fat_size} bytes")

    # Read FAT entries
    # Each FAT entry is 8 bytes: start offset (4 bytes), end offset (4 bytes)
    num_files = fat_size // 8
    fat_entries = []
    for i in range(num_files):
        entry_offset = fat_offset + i * 8
        start, end = struct.unpack('<II', rom_data[entry_offset:entry_offset+8])
        fat_entries.append((start, end))

    # Read Directory Table (FNT Main Table)
    # Root entry is at fnt_offset.
    # Entry format: subtable_offset (4 bytes), first_file_id (2 bytes), parent_id (2 bytes)
    # For root, parent_id is the total number of directories.
    subtable_offset, first_file_id, total_dirs = struct.unpack('<IHH', rom_data[fnt_offset:fnt_offset+8])
    print(f"Total directories in ROM: {total_dirs}")
    print(f"Total files in ROM (FAT): {num_files}")

    dir_entries = []
    for i in range(total_dirs):
        entry_offset = fnt_offset + i * 8
        sub_off, f_id, p_id = struct.unpack('<IHH', rom_data[entry_offset:entry_offset+8])
        dir_entries.append({
            'dir_id': 0xF000 + i,
            'subtable_offset': sub_off,
            'first_file_id': f_id,
            'parent_id': p_id,
            'name': '',
            'files': [],
            'subdirs': []
        })

    # The first directory (0xF000) is the root directory
    dir_entries[0]['name'] = 'root'

    # Now we process the sub-tables to build the tree and assign names to directories and files
    # The subtable offset is relative to fnt_offset.
    for i in range(total_dirs):
        dir_info = dir_entries[i]
        curr_offset = fnt_offset + dir_info['subtable_offset']
        
        file_id_counter = dir_info['first_file_id']
        
        while True:
            type_len = rom_data[curr_offset]
            curr_offset += 1
            
            if type_len == 0x00:
                break # End of directory sub-table
            
            is_dir = bool(type_len & 0x80)
            name_len = type_len & 0x7F
            
            name = rom_data[curr_offset : curr_offset + name_len].decode('ascii', errors='ignore')
            curr_offset += name_len
            
            if is_dir:
                sub_dir_id = struct.unpack('<H', rom_data[curr_offset : curr_offset + 2])[0]
                curr_offset += 2
                
                # Assign the name of the subdirectory and record the parent-child relationship
                sub_dir_idx = sub_dir_id - 0xF000
                if 0 <= sub_dir_idx < len(dir_entries):
                    dir_entries[sub_dir_idx]['name'] = name
                dir_info['subdirs'].append((name, sub_dir_id))
            else:
                # File entry
                dir_info['files'].append((name, file_id_counter))
                file_id_counter += 1

    # Traverse the directory tree to construct full paths for files
    file_paths = {} # file_id -> relative_path
    
    def resolve_paths(dir_idx, current_path):
        dir_info = dir_entries[dir_idx]
        
        # Add files in this directory
        for filename, file_id in dir_info['files']:
            file_paths[file_id] = os.path.join(current_path, filename)
            
        # Recurse into subdirectories
        for name, sub_dir_id in dir_info['subdirs']:
            sub_dir_idx = sub_dir_id - 0xF000
            resolve_paths(sub_dir_idx, os.path.join(current_path, name))

    resolve_paths(0, "")

    # Now let's extract the files to out_dir
    os.makedirs(out_dir, exist_ok=True)
    
    # Save a file list manifest
    manifest_path = os.path.join(out_dir, "manifest.txt")
    manifest_lines = []
    
    extracted_count = 0
    print(f"Extracting files to '{out_dir}'...")
    
    for file_id, rel_path in sorted(file_paths.items()):
        if file_id >= len(fat_entries):
            print(f"Warning: File ID {file_id} is out of range for FAT (size {len(fat_entries)})")
            continue
            
        start, end = fat_entries[file_id]
        size = end - start
        
        manifest_lines.append(f"ID: {file_id:04d} | Offset: 0x{start:08X} - 0x{end:08X} | Size: {size:8d} bytes | Path: {rel_path}\n")
        
        if size < 0:
            print(f"Warning: File ID {file_id} has negative size ({size})")
            continue
            
        # Write file content
        file_out_path = os.path.join(out_dir, rel_path)
        os.makedirs(os.path.dirname(file_out_path), exist_ok=True)
        
        with open(file_out_path, 'wb') as out_f:
            out_f.write(rom_data[start:end])
            
        extracted_count += 1
        if extracted_count % 100 == 0:
            print(f"Extracted {extracted_count}/{len(file_paths)} files...")

    # Write manifest file
    with open(manifest_path, 'w') as mf:
        mf.writelines(manifest_lines)

    print(f"Extraction completed. Extracted {extracted_count} files.")
    print(f"Manifest written to {manifest_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nds_unpack.py <rom_path> <output_dir>")
        sys.exit(1)
        
    parse_nds(sys.argv[1], sys.argv[2])

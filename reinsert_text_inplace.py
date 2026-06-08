#!/usr/bin/env python3
import sys
import struct
import os
import csv

sys.path.insert(0, '/Users/acr/Library/Python/3.9/lib/python/site-packages')
from hacktools import cpk, common

CSV_FILES = [
    "/Users/acr/Develop/sigma-harmonics/dialogue_story.csv",
    "/Users/acr/Develop/sigma-harmonics/menu_ui.csv",
    "/Users/acr/Develop/sigma-harmonics/tutorials.csv"
]
ORIG_CPK_DIR = "/Users/acr/Develop/sigma-harmonics/extracted_cpk"
MOD_CPK_DIR = "/Users/acr/Develop/sigma-harmonics/modified_cpk"

if not os.path.exists(MOD_CPK_DIR):
    os.makedirs(MOD_CPK_DIR)

translations_by_file = {}
file_types = {}

def remove_nul(stream):
    for line in stream:
        yield line.replace('\x00', '')

for csv_path in CSV_FILES:
    if not os.path.exists(csv_path):
        continue
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(remove_nul(f))
        for row in reader:
            if not row.get('English') or not row['English'].strip():
                continue
            bin_name = row['File']
            if not bin_name.endswith('.bin'): bin_name += '.bin'
            file_types[bin_name] = row['Type']
            if bin_name not in translations_by_file:
                translations_by_file[bin_name] = []
            translations_by_file[bin_name].append(row)

def reinsert_table_inplace(file_path, file_translations):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    first_off = struct.unpack('<I', data[0:4])[0]
    num_strings = first_off // 8
    
    entries = []
    for s in range(num_strings):
        ent_off = s * 8
        offset, length = struct.unpack('<II', data[ent_off : ent_off + 8])
        entries.append((offset, length))
        
    trans_map = {}
    for row in file_translations:
        if row['Index'].strip():
            trans_map[int(row['Index'])] = row
            
    new_data = bytearray(data)
    
    for s in range(num_strings):
        orig_off, orig_len = entries[s]
        orig_bytes = data[orig_off : orig_off + orig_len]
        
        trans_row = trans_map.get(s)
        if trans_row and trans_row['English'].strip():
            trans_text = trans_row['English'].replace('\\n', '\n').replace('\\r', '\r')
            
            # Assume utf-8 based on original string decode
            encoding = 'utf-8'
            try:
                if orig_bytes:
                    orig_bytes.decode('utf-8')
            except:
                encoding = 'utf-16-le'
                
            trans_bytes = trans_text.encode(encoding)
            
            if orig_bytes and orig_bytes[-1] == 0:
                trans_bytes += b'\x00'
                
            if len(trans_bytes) <= orig_len:
                new_data[orig_off:orig_off+len(trans_bytes)] = trans_bytes
                new_data[orig_off+len(trans_bytes):orig_off+orig_len] = b'\x00' * (orig_len - len(trans_bytes))
                struct.pack_into('<II', new_data, s * 8, orig_off, len(trans_bytes))
            else:
                return None # Overflow!
    return bytes(new_data)

def reinsert_robust_inplace(file_path, file_translations):
    with open(file_path, 'rb') as f:
        new_data = bytearray(f.read())
    
    for row in file_translations:
        orig_text = row['Japanese']
        trans_text = row['English']
        
        orig_text_clean = orig_text.replace('\n', '')
        trans_text_clean = trans_text.replace('\n', '')
        
        orig_bytes = orig_text_clean.encode('utf-8')
        trans_bytes = trans_text_clean.encode('utf-8')
        
        orig_offset = new_data.find(orig_bytes)
        if orig_offset != -1:
            if len(trans_bytes) <= len(orig_bytes):
                new_data[orig_offset:orig_offset+len(trans_bytes)] = trans_bytes
                new_data[orig_offset+len(trans_bytes):orig_offset+len(orig_bytes)] = b'\x00' * (len(orig_bytes) - len(trans_bytes))
            else:
                return None # Overflow!
    return new_data

modified_count = 0
for bin_name, file_trans in translations_by_file.items():
    orig_file_path = os.path.join(ORIG_CPK_DIR, bin_name)
    if not os.path.exists(orig_file_path):
        continue
        
    file_type = file_types[bin_name]
    
    new_bytes = None
    if file_type == 'Table':
        new_bytes = reinsert_table_inplace(orig_file_path, file_trans)
    elif file_type == 'Robust':
        new_bytes = reinsert_robust_inplace(orig_file_path, file_trans)
        
    print(f"File {bin_name} returned None!" if new_bytes is None else f"File {bin_name} was modified!")

    if new_bytes is not None:
        mod_file_path = os.path.join(MOD_CPK_DIR, bin_name)
        with open(mod_file_path, 'wb') as f:
            f.write(new_bytes)
        modified_count += 1
    else:
        # Overflowed, so we do NOT write it to modified_cpk.
        # It will gracefully fallback to original Japanese!
        pass

print(f"Successfully generated {modified_count} valid in-place modified files.")

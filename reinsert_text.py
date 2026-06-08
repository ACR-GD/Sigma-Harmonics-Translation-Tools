import os
import csv
import struct
import hacktools.cpk
import hacktools.nds

CSV_FILES = [
    '/Users/acr/Develop/sigma-harmonics/dialogue_story.csv',
    '/Users/acr/Develop/sigma-harmonics/menu_ui.csv',
    '/Users/acr/Develop/sigma-harmonics/tutorials.csv'
]

ORIG_CPK_DIR = '/Users/acr/Develop/sigma-harmonics/extracted_cpk/'
MOD_CPK_DIR = '/Users/acr/Develop/sigma-harmonics/modified_cpk/'

os.makedirs(MOD_CPK_DIR, exist_ok=True)

# 1. Load all translations from CSV files
translations_by_file = {}
file_types = {}

def remove_nul(stream):
    for line in stream:
        yield line.replace('\x00', '')

for csv_path in CSV_FILES:
    if not os.path.exists(csv_path):
        print(f"Warning: CSV not found: {csv_path}")
        continue
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(remove_nul(f))
        for row in reader:
            filename = row['File']
            bin_name = filename + '.bin'
            file_types[bin_name] = row['Type']
            if bin_name not in translations_by_file:
                translations_by_file[bin_name] = []
            translations_by_file[bin_name].append(row)

print(f"Loaded translations for {len(translations_by_file)} files.")

def reinsert_table(file_path, file_translations):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    first_off = struct.unpack('<I', data[0:4])[0]
    num_strings = first_off // 8
    
    # Read table entries
    entries = []
    for s in range(num_strings):
        ent_off = s * 8
        offset, length = struct.unpack('<II', data[ent_off : ent_off + 8])
        entries.append((offset, length))
        
    last_orig_offset = max(offset + length for offset, length in entries) if entries else first_off
    remaining_data = data[last_orig_offset:]
    
    new_data = bytearray(first_off)
    
    # Index translations by Index (int)
    trans_map = {}
    for row in file_translations:
        if row['Index'].strip():
            trans_map[int(row['Index'])] = row
            
    for s in range(num_strings):
        orig_off, orig_len = entries[s]
        orig_bytes = data[orig_off : orig_off + orig_len]
        
        has_null = False
        if orig_bytes and orig_bytes[-1] == 0:
            orig_bytes_key = orig_bytes[:-1]
            has_null = True
        else:
            orig_bytes_key = orig_bytes
            
        orig_text = None
        encoding = 'utf-8'
        try:
            orig_text = orig_bytes_key.decode('utf-8')
        except UnicodeDecodeError:
            try:
                orig_text = orig_bytes_key.decode('utf-16-le')
                encoding = 'utf-16-le'
            except UnicodeDecodeError:
                pass
                
        trans_row = trans_map.get(s)
        if trans_row and trans_row['English'].strip():
            trans_text = trans_row['English']
            trans_text = trans_text.replace('\\n', '\n').replace('\\r', '\r')
            trans_bytes = trans_text.encode(encoding)
        else:
            trans_bytes = orig_bytes_key
            
        if has_null:
            trans_bytes = trans_bytes + b'\x00'
            
        new_offset = len(new_data)
        new_length = len(trans_bytes)
        new_data.extend(trans_bytes)
        
        struct.pack_into('<II', new_data, s * 8, new_offset, new_length)
        
    new_data.extend(remaining_data)
    return bytes(new_data)

def reinsert_robust(file_path, file_translations):
    with open(file_path, 'rb') as f:
        data = bytearray(f.read())
        
    # Sort descending by offset to avoid shifting bytes before them
    sorted_trans = sorted(file_translations, key=lambda r: int(r['Offset'], 16), reverse=True)
    
    for row in sorted_trans:
        offset = int(row['Offset'], 16)
        jp_text = row['Japanese']
        en_text = row['English']
        
        if not en_text.strip():
            continue
            
        orig_text_clean = jp_text.replace('\\n', '\n').replace('\\r', '\r')
        orig_bytes = orig_text_clean.encode('utf-8')
        
        orig_len = len(orig_bytes)
        file_slice = data[offset : offset + orig_len]
        
        if file_slice != orig_bytes:
            # Safe fallbacks or minor byte matching checks can be implemented here
            continue
            
        trans_text_clean = en_text.replace('\\n', '\n').replace('\\r', '\r')
        trans_bytes = trans_text_clean.encode('utf-8')
        
        is_null_terminated = False
        if offset + orig_len < len(data) and data[offset + orig_len] == 0:
            is_null_terminated = True
            
        if is_null_terminated:
            trans_bytes = trans_bytes + b'\x00'
            orig_len_with_null = orig_len + 1
        else:
            orig_len_with_null = orig_len
            
        data[offset : offset + orig_len_with_null] = trans_bytes
        
    return bytes(data)

# 2. Reinsert strings and save to MOD_CPK_DIR
print("Reinserting translations into binary files...")
modified_count = 0
for bin_name, file_trans in translations_by_file.items():
    orig_file_path = os.path.join(ORIG_CPK_DIR, bin_name)
    if not os.path.exists(orig_file_path):
        continue
        
    file_type = file_types[bin_name]
    
    if file_type == 'Table':
        new_bytes = reinsert_table(orig_file_path, file_trans)
    elif file_type == 'Robust':
        new_bytes = reinsert_robust(orig_file_path, file_trans)
    else:
        continue
        
    mod_file_path = os.path.join(MOD_CPK_DIR, bin_name)
    with open(mod_file_path, 'wb') as f:
        f.write(new_bytes)
    modified_count += 1

print(f"Modified and saved {modified_count} binary files to {MOD_CPK_DIR}.")

# 3. Repack CPK
print("\nRepacking CPK archive...")
orig_cpk = "/Users/acr/Develop/sigma-harmonics/extracted_rom/data/data/data.cpk"
new_cpk = "/Users/acr/Develop/sigma-harmonics/rom_work/data/data/data.cpk"

hacktools.cpk.repack(orig_cpk, new_cpk, ORIG_CPK_DIR, MOD_CPK_DIR)
print("CPK repackaged successfully!")

# 4. Repack ROM
print("\nRepacking ROM...")
rom_file = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
new_rom = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"
work_folder = "/Users/acr/Develop/sigma-harmonics/rom_work/"

hacktools.nds.repackRom(rom_file, new_rom, work_folder)
print(f"\nROM repacked successfully! Output path: {new_rom}")

#!/usr/bin/env python3
import os
import sys
import csv
import struct

def extract_table_strings(data):
    # Reads the pointer table at offset 0
    first_off = struct.unpack('<I', data[0:4])[0]
    if first_off == 0 or first_off % 8 != 0 or first_off > len(data):
        return None
        
    num_strings = first_off // 8
    entries = []
    
    for s in range(num_strings):
        ent_off = s * 8
        if ent_off + 8 > len(data):
            return None
        offset, length = struct.unpack('<II', data[ent_off : ent_off + 8])
        if offset + length > len(data):
            return None
        entries.append((offset, length))
        
    strings = []
    for idx, (offset, length) in enumerate(entries):
        str_bytes = data[offset : offset + length]
        if str_bytes and str_bytes[-1] == 0:
            str_bytes = str_bytes[:-1]
            
        # Try UTF-8 first, fallback to UTF-16LE, then ignore
        try:
            text = str_bytes.decode('utf-8')
            strings.append((offset, idx, text))
        except:
            try:
                text = str_bytes.decode('utf-16-le')
                strings.append((offset, idx, text))
            except:
                pass
    return strings

def extract_robust_strings(data, min_japanese_chars=2):
    strings = []
    i = 0
    while i < len(data):
        start = i
        japanese_char_count = 0
        current_str = []
        
        while i < len(data):
            is_japanese = False
            char_len = 0
            if data[i] == 0xE3:
                char_len = 3
            elif 0xE4 <= data[i] <= 0xE9:
                char_len = 3
            elif data[i] == 0x01 or data[i] == 0xEF: # Full-width forms
                char_len = 3
                
            if char_len > 0 and i + char_len <= len(data):
                try:
                    char_bytes = data[i:i+char_len]
                    char = char_bytes.decode('utf-8')
                    val = ord(char)
                    if (0x3000 <= val <= 0x30FF) or (0x4E00 <= val <= 0x9FFF) or (0xFF00 <= val <= 0xFFEF):
                        is_japanese = True
                except:
                    pass
            
            if is_japanese:
                current_str.append(data[i:i+char_len].decode('utf-8'))
                japanese_char_count += 1
                i += char_len
            elif 32 <= data[i] < 127 or data[i] in [9, 10, 13]:
                char = chr(data[i])
                if char == '\n':
                    current_str.append('\\n')
                elif char == '\r':
                    current_str.append('\\r')
                else:
                    current_str.append(char)
                i += 1
            else:
                break
                
        if japanese_char_count >= min_japanese_chars:
            text = "".join(current_str).strip()
            if len(text) >= 2:
                strings.append((start, None, text))
                
        if i == start:
            i += 1
            
    return strings

def get_category(file_name, data, strings):
    # 1. Dialogue/Story heuristics
    if data.startswith(b'Sigma') or data.startswith(b'sigma'):
        return "dialogue_story"
        
    file_id = int(''.join(c for c in file_name if c.isdigit()))
    
    # Range based categorization
    if 4000 <= file_id < 4500:
        return "dialogue_story"
    elif 4500 <= file_id < 4800:
        # Check if contains dialogue quotes or particles
        combined_text = "".join(s[2] for s in strings)
        if any(q in combined_text for q in ['「', '」', 'よ。', 'ね。', 'っす', 'だ。']):
            return "dialogue_story"
        return "menu_ui"
    elif 4800 <= file_id < 5000:
        return "tutorials"
    elif 5000 <= file_id < 5600:
        # Menus & UI
        combined_text = "".join(s[2] for s in strings)
        if "チュートリアル" in combined_text or "操作" in combined_text:
            return "tutorials"
        return "menu_ui"
        
    return "menu_ui"

def main():
    dir_path = "extracted_cpk"
    if not os.path.exists(dir_path):
        print(f"Error: Directory '{dir_path}' does not exist.")
        sys.exit(1)
        
    print(f"Extracting text from files in '{dir_path}'...")
    
    dialogue_rows = []
    menu_rows = []
    tutorial_rows = []
    
    files = sorted(os.listdir(dir_path))
    processed_count = 0
    
    for file in files:
        if not file.endswith('.bin'):
            continue
            
        file_path = os.path.join(dir_path, file)
        with open(file_path, 'rb') as f:
            data = f.read()
            
        if len(data) < 8:
            continue
            
        # Filter: Skip files with no/low hiragana count, or out-of-range file IDs (to avoid graphics/audio noise)
        file_id = int(''.join(c for c in file if c.isdigit()))
        if file_id < 4000 or file_id > 5600:
            continue
            
        sjis_hira = sum(1 for i in range(len(data)-1) if data[i] == 0x82 and (0x9F <= data[i+1] <= 0xF1))
        utf8_hira = sum(1 for i in range(len(data)-2) if data[i] == 0xE3 and (data[i+1] == 0x81 or data[i+1] == 0x82))
        utf16_hira = sum(1 for i in range(len(data)-1) if data[i+1] == 0x30 and (0x40 <= data[i] <= 0x9F))
        
        max_hira = max(sjis_hira, utf8_hira, utf16_hira)
        if max_hira < 3:
            continue
            
        # Try table format first
        strings = extract_table_strings(data)
        extraction_type = "Table"
        
        # Fallback to robust scanner if table parsing returned nothing
        if not strings:
            strings = extract_robust_strings(data)
            extraction_type = "Robust"
            
        if not strings:
            continue
            
        category = get_category(file, data, strings)
        
        file_base = os.path.splitext(file)[0]
        
        for offset, idx, text in strings:
            # Skip dummy or very short placeholder strings
            if text in ['ダミー', 'ない', 'なし', '……']:
                continue
                
            # Filter out robust noise (garbage binary matching Japanese ranges)
            if extraction_type == "Robust":
                # Check for noise characters
                if any(c in text for c in ['峀', '叆', '賮', '迶', '窖', '笾']):
                    continue
                # Must contain at least one Hiragana, Katakana, or full-width punctuation/symbol
                has_japanese_markers = False
                for char in text:
                    val = ord(char)
                    if (0x3040 <= val <= 0x30FF) or (0xFF00 <= val <= 0xFFEF):
                        has_japanese_markers = True
                        break
                if not has_japanese_markers:
                    continue
                
            row = {
                'File': file_base,
                'Type': extraction_type,
                'Offset': f"0x{offset:04X}",
                'Index': idx if idx is not None else "",
                'Japanese': text,
                'English': ""
            }
            
            if category == "dialogue_story":
                dialogue_rows.append(row)
            elif category == "tutorials":
                tutorial_rows.append(row)
            else:
                menu_rows.append(row)
                
        processed_count += 1
        
    # Write CSV files
    headers = ['File', 'Type', 'Offset', 'Index', 'Japanese', 'English']
    
    csv_configs = [
        ('dialogue_story.csv', dialogue_rows),
        ('menu_ui.csv', menu_rows),
        ('tutorials.csv', tutorial_rows)
    ]
    
    for csv_file, rows in csv_configs:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(rows)} rows to {csv_file}")
        
    print(f"\nText extraction complete! Processed {processed_count} text files.")

if __name__ == "__main__":
    main()

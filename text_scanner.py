#!/usr/bin/env python3
import os
import sys

def scan_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
        
    results = {}
    
    # 1. Check Shift-JIS hiragana count
    # Hiragana in Shift-JIS are 2 bytes:
    # First byte is 0x82
    # Second byte is 0x9F to 0xF1
    sjis_hira_count = 0
    i = 0
    while i < len(data) - 1:
        if data[i] == 0x82 and (0x9F <= data[i+1] <= 0xF1):
            sjis_hira_count += 1
            i += 2
        else:
            i += 1
            
    if sjis_hira_count > 0:
        results['Shift-JIS'] = sjis_hira_count

    # 2. Check UTF-8 hiragana count
    # Hiragana in UTF-8 are 3 bytes starting with 0xE3 0x81 or 0xE3 0x82
    utf8_hira_count = 0
    i = 0
    while i < len(data) - 2:
        if data[i] == 0xE3 and (data[i+1] == 0x81 or data[i+1] == 0x82):
            utf8_hira_count += 1
            i += 3
        else:
            i += 1
            
    if utf8_hira_count > 0:
        results['UTF-8'] = utf8_hira_count

    # 3. Check UTF-16LE hiragana count
    # Hiragana in UTF-16LE: second byte is 0x30, first byte is 0x40 to 0x9F
    utf16_hira_count = 0
    i = 0
    while i < len(data) - 1:
        if data[i+1] == 0x30 and (0x40 <= data[i] <= 0x9F):
            utf16_hira_count += 1
            i += 2
        else:
            i += 2 # alignment
            
    if utf16_hira_count > 0:
        results['UTF-16LE'] = utf16_hira_count
        
    return results

def get_text_preview(file_path, encoding, max_len=100):
    with open(file_path, 'rb') as f:
        data = f.read()
        
    if encoding == 'Shift-JIS':
        # Decode strings of Shift-JIS characters
        decoded = []
        i = 0
        current_str = []
        while i < len(data):
            # Check for SJIS double byte
            is_sjis = False
            if (0x81 <= data[i] <= 0x9F) or (0xE0 <= data[i] <= 0xFC):
                if i + 1 < len(data) and ((0x40 <= data[i+1] <= 0x7E) or (0x80 <= data[i+1] <= 0xFC)):
                    is_sjis = True
            # Check for half-width kana
            is_half_kana = (0xA1 <= data[i] <= 0xDF)
            # Check for printable ASCII
            is_ascii = (32 <= data[i] < 127) or (data[i] == 10) or (data[i] == 13)
            
            if is_sjis:
                try:
                    char = data[i:i+2].decode('shift-jis')
                    current_str.append(char)
                except:
                    pass
                i += 2
            elif is_half_kana:
                try:
                    char = data[i:i+1].decode('shift-jis')
                    current_str.append(char)
                except:
                    pass
                i += 1
            elif is_ascii:
                current_str.append(chr(data[i]))
                i += 1
            else:
                if len(current_str) >= 3:
                    decoded.append("".join(current_str))
                current_str = []
                i += 1
        if len(current_str) >= 3:
            decoded.append("".join(current_str))
            
        # Filter and join
        preview = " | ".join(s.strip() for s in decoded if s.strip())
        return preview[:max_len]
        
    elif encoding == 'UTF-8':
        try:
            # Simple utf-8 decoding of printable segments
            decoded = data.decode('utf-8', errors='ignore')
            clean = "".join(c if (ord(c) >= 32 or c in '\n\r') else ' ' for c in decoded)
            return " ".join(clean.split())[:max_len]
        except:
            return ""
            
    elif encoding == 'UTF-16LE':
        try:
            decoded = data.decode('utf-16-le', errors='ignore')
            clean = "".join(c if (ord(c) >= 32 or c in '\n\r') else ' ' for c in decoded)
            return " ".join(clean.split())[:max_len]
        except:
            return ""
            
    return ""

def scan_dir(dir_path):
    print(f"Scanning directory: {dir_path}")
    text_files = []
    
    for root, dirs, files in os.walk(dir_path):
        for file in sorted(files):
            if not file.endswith('.bin'):
                continue
            file_path = os.path.join(root, file)
            res = scan_file(file_path)
            
            if res:
                # Find best encoding (max hiragana count)
                best_enc = max(res, key=res.get)
                count = res[best_enc]
                if count >= 3: # require at least 3 hiragana to reduce noise
                    text_files.append((file, best_enc, count, file_path))
                    
    # Sort by hiragana count descending
    text_files.sort(key=lambda x: x[2], reverse=True)
    
    print(f"\nFound {len(text_files)} files potentially containing Japanese text.")
    print(f"{'File ID':12s} | {'Encoding':10s} | {'Hira Count':10s} | {'Preview'}")
    print("-" * 80)
    
    for file, enc, count, path in text_files[:40]: # show top 40
        preview = get_text_preview(path, enc)
        print(f"{file:12s} | {enc:10s} | {count:10d} | {preview}")

if __name__ == "__main__":
    scan_dir("extracted_cpk")

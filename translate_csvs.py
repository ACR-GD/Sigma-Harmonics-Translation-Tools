import os
import re
import csv
import json
import html
import urllib.request

ENV_PATH = '/Users/acr/Develop/sigma-harmonics/.env'
CSV_FILES = [
    '/Users/acr/Develop/sigma-harmonics/dialogue_story.csv',
    '/Users/acr/Develop/sigma-harmonics/menu_ui.csv',
    '/Users/acr/Develop/sigma-harmonics/tutorials.csv'
]
BATCH_SIZE = 50

# Load API key
api_key = None
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('GOOGLE_API_KEY='):
                api_key = line.split('=', 1)[1].strip()

if not api_key:
    print(f"Error: GOOGLE_API_KEY not found in {ENV_PATH}")
    exit(1)

def is_clean_japanese(text):
    if not text.strip():
        return False
    # If purely ASCII/spaces/simple punctuation, skip translation
    if re.match(r'^[a-zA-Z0-9\s\-_.,!?()\'"\[\]$:\\/]*$', text):
        return False
    # Private Use Area (often garbage bytes in game extraction)
    if re.search(r'[\ue000-\uf8ff]', text):
        return False
    
    # Valid Japanese range check (Hiragana, Katakana, CJK Unified Ideographs, Fullwidth punctuation/letters)
    if re.search(r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uffef\u4e00-\u9fff]', text):
        valid_chars = 0
        for char in text:
            o = ord(char)
            # ASCII, CJK Unified, Hiragana/Katakana/Fullwidth symbols
            if (32 <= o <= 126) or o in (9, 10, 13) or (0x4e00 <= o <= 0x9fff) or (0x3000 <= o <= 0x30ff) or (0xff00 <= o <= 0xffef):
                valid_chars += 1
        ratio = valid_chars / len(text)
        return ratio > 0.8
    return False

def pre_process(text):
    # Protect $cXX formatting codes by wrapping them in notranslate span
    text = re.sub(r'\$c(\d+)', r'<span class="notranslate">c\1</span>', text)
    # Protect standard color code templates if any, or other controls
    # Protect literal \n and \r
    text = text.replace('\\n', '<br/>')
    text = text.replace('\\r', '<br class="r"/>')
    return text

def post_process(translated):
    # Unescape HTML entities returned by the translation API
    translated = html.unescape(translated)
    # Restore \r
    translated = re.sub(r'<br\s+class=["\']r["\']\s*/?>', r'\\r', translated, flags=re.IGNORECASE)
    # Restore \n
    translated = re.sub(r'<br\s*/?>', r'\\n', translated, flags=re.IGNORECASE)
    # Restore $cXX (matches any span structure regardless of reordered attributes)
    translated = re.sub(r'<span[^>]*>\s*c(\d+)\s*</span>', r'$c\1', translated, flags=re.IGNORECASE)
    return translated

def translate_batch(texts):
    if not texts:
        return []
    processed_texts = [pre_process(t) for t in texts]
    url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    data = {
        "q": processed_texts,
        "target": "en",
        "source": "ja",
        "format": "html"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            translations = res_data['data']['translations']
            return [post_process(t['translatedText']) for t in translations]
    except Exception as e:
        print(f"\nAPI Error during batch translation: {e}")
        if hasattr(e, 'read'):
            try:
                print("Response detail:", e.read().decode('utf-8'))
            except:
                pass
        return None

def process_file(csv_path):
    print(f"\nProcessing {os.path.basename(csv_path)}...")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    # Read existing rows
    rows = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        # Strip out NUL bytes which cause DictReader to crash
        clean_lines = (line.replace('\x00', '') for line in f)
        reader = csv.DictReader(clean_lines)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    if not fieldnames:
        print("Empty or invalid header in CSV")
        return

    # Identify rows that need translation
    to_translate_indices = []
    texts_to_translate = []
    
    for i, row in enumerate(rows):
        jp_text = row.get('Japanese', '')
        en_text = row.get('English', '')
        
        # Translate if it is valid Japanese and English translation is empty
        if is_clean_japanese(jp_text) and not en_text.strip():
            to_translate_indices.append(i)
            texts_to_translate.append(jp_text)

    total_needed = len(texts_to_translate)
    print(f"Found {total_needed} rows needing translation.")
    if total_needed == 0:
        print("Nothing to translate for this file.")
        return

    # Translate in batches
    translated_count = 0
    for start_idx in range(0, total_needed, BATCH_SIZE):
        batch_indices = to_translate_indices[start_idx : start_idx + BATCH_SIZE]
        batch_texts = texts_to_translate[start_idx : start_idx + BATCH_SIZE]
        
        print(f"Translating batch {start_idx // BATCH_SIZE + 1}/{(total_needed + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch_texts)} items)...", end="", flush=True)
        translated_texts = translate_batch(batch_texts)
        
        if translated_texts is None:
            print(" [Failed! stopping file processing]")
            break
            
        # Update rows in-memory
        for idx, trans_text in zip(batch_indices, translated_texts):
            rows[idx]['English'] = trans_text
            
        translated_count += len(batch_texts)
        print(" [Done]")

        # Write progress immediately to a temp file and rename (atomic save)
        temp_path = csv_path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_path, csv_path)

    print(f"Finished processing. Translated {translated_count} of {total_needed} rows.")

if __name__ == "__main__":
    for csv_file in CSV_FILES:
        process_file(csv_file)
    print("\nAll files processed successfully!")

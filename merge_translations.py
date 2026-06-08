#!/usr/bin/env python3
import csv
import os

def remove_nul(stream):
    for line in stream:
        yield line.replace('\x00', '')

files = ['dialogue_story.csv', 'menu_ui.csv', 'tutorials.csv']

for f in files:
    old_f = os.path.join('/Users/acr/Develop/sigma-harmonics/csv_backup', f)
    new_f = os.path.join('/Users/acr/Develop/sigma-harmonics', f)
    
    if not os.path.exists(old_f): continue
    
    # load translations
    translations = {}
    with open(old_f, 'r', encoding='utf-8') as old_file:
        reader = csv.DictReader(remove_nul(old_file))
        for row in reader:
            if row['English'].strip():
                # Key by File + Japanese to be safe
                key = (row['File'], row['Japanese'].strip())
                translations[key] = row['English']
                
    # update new
    new_rows = []
    headers = []
    with open(new_f, 'r', encoding='utf-8') as new_file:
        reader = csv.DictReader(remove_nul(new_file))
        headers = reader.fieldnames
        for row in reader:
            key = (row['File'], row['Japanese'].strip())
            if key in translations:
                row['English'] = translations[key]
            new_rows.append(row)
            
    with open(new_f, 'w', encoding='utf-8', newline='') as out_file:
        writer = csv.DictWriter(out_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(new_rows)
        
    print(f"Merged translations for {f}")

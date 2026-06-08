#!/usr/bin/env python3
import sys
import struct
import csv
sys.path.insert(0, '/Users/acr/Develop/sigma-harmonics')
import reinsert_text

def remove_nul(stream):
    for line in stream:
        yield line.replace('\x00', '')

# Load CSV
trans = []
with open('/Users/acr/Develop/sigma-harmonics/dialogue_story.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(remove_nul(f))
    for row in reader:
        if row['File'] == 'ID04025':
            trans.append(row)

# Reinsert
new_bytes = reinsert_text.reinsert_robust('/tmp/ID04025_clean.bin', trans)
with open('/tmp/ID04025_mod.bin', 'wb') as f:
    f.write(new_bytes)

# Compress
import hacktools.cmp_cri as cmp_cri
comp = cmp_cri.compressCRILAYLA(new_bytes)
print(f"Original Raw: 27848")
print(f"Modified Raw: {len(new_bytes)}")
print(f"Original Comp: 13436")
print(f"Modified Comp: {len(comp)}")

#!/usr/bin/env python3
import sys

csv_files = [
    '/Users/acr/Develop/sigma-harmonics/dialogue_story.csv',
    '/Users/acr/Develop/sigma-harmonics/menu_ui.csv',
    '/Users/acr/Develop/sigma-harmonics/tutorials.csv'
]

for c in csv_files:
    with open(c, 'r', encoding='utf-8') as f:
        for line in f:
            if 'ID04030' in line:
                print(f"Found 4030 in {c}: {line.strip()[:100]}...")
            if 'ID4198' in line:
                print(f"Found 4198 in {c}: {line.strip()[:100]}...")

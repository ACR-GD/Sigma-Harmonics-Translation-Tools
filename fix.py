with open('/Users/acr/Develop/sigma-harmonics/reinsert_text_inplace.py', 'r') as f:
    text = f.read()
text = text.replace("bin_name = row['File']", "bin_name = row['File']\n            if not bin_name.endswith('.bin'): bin_name += '.bin'")
with open('/Users/acr/Develop/sigma-harmonics/reinsert_text_inplace.py', 'w') as f:
    f.write(text)

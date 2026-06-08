#!/usr/bin/env python3
import ndspy.rom
import sys

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
out_rom = "/Users/acr/Develop/sigma-harmonics/sigma_en_final.nds"
new_cpk = "/Users/acr/Develop/sigma-harmonics/data_new.cpk"

print("Loading original ROM via ndspy...")
rom = ndspy.rom.NintendoDSRom.fromFile(orig_rom)

print("Loading new CPK...")
with open(new_cpk, 'rb') as f:
    cpk_data = f.read()

# Replace data.cpk. We assume it is the first file in the root directory.
# We can find its index by name:
file_id = 0
print(f"data.cpk is file ID: {file_id}")

print("Replacing data...")
rom.files[file_id] = cpk_data

print("Saving new ROM... (This will properly rebuild FAT/FNT)")
rom.saveToFile(out_rom)
print(f"Saved to {out_rom}")

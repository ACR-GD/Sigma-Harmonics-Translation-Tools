import sys
import os
sys.path.append('/Users/acr/Library/Python/3.9/lib/python/site-packages')
import hacktools.nds

orig_rom = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
target_rom = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_en.nds"
work_folder = "/Users/acr/Develop/sigma-harmonics/rom_work/"

print("Repacking translated ROM...")
hacktools.nds.repackRom(orig_rom, target_rom, work_folder)

print("Patching offset 0x1000 to zero and padding to 128MB...")
if os.path.exists(target_rom):
    with open(target_rom, 'r+b') as f:
        # Patch offset 0x1000
        f.seek(0x1000)
        f.write(b'\x00\x00\x00\x00')
        
        # Pad to 134217728 bytes (128 MB)
        f.seek(0, 2) # Go to end
        current_size = f.tell()
        target_size = 134217728
        if current_size < target_size:
            padding_needed = target_size - current_size
            print(f"Padding ROM from {current_size} to {target_size} bytes (adding {padding_needed} bytes of 0xFF)...")
            f.write(b'\xFF' * padding_needed)
        else:
            print(f"ROM size is already {current_size} bytes (no padding needed).")
    print("Repack and fix completed successfully!")
else:
    print("Error: Target ROM was not created!")

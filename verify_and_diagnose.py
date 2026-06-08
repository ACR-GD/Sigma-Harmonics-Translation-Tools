#!/usr/bin/env python3
"""
Step 1: Verify original ROM integrity and back it up.
Step 2: Compare original data.cpk (from ROM) with our repacked data.cpk structure.
"""
import struct
import hashlib
import shutil
import os

ORIG_ROM = "/Users/acr/Develop/sigma-harmonics/2581 - Sigma Harmonics (J)(Independent)/2581 - Sigma Harmonics (J)(Independent).nds"
BACKUP_ROM = "/Users/acr/Develop/sigma-harmonics/sigma_harmonics_original_backup.nds"
NEW_CPK = "/Users/acr/Develop/sigma-harmonics/rom_work/data/data/data.cpk"

print("=" * 60)
print("STEP 1: Verify original ROM")
print("=" * 60)

with open(ORIG_ROM, 'rb') as f:
    orig_data = f.read()

md5 = hashlib.md5(orig_data).hexdigest()
sha1 = hashlib.sha1(orig_data).hexdigest()
print(f"  Size: {len(orig_data):,} bytes")
print(f"  MD5:  {md5}")
print(f"  SHA1: {sha1}")

# Verify header CRC
def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

header_crc_computed = crc16(orig_data[0:0x15E])
header_crc_stored = struct.unpack_from('<H', orig_data, 0x15E)[0]
print(f"  Header CRC stored:   0x{header_crc_stored:04X}")
print(f"  Header CRC computed: 0x{header_crc_computed:04X}")
print(f"  Header CRC valid:    {'YES ✓' if header_crc_stored == header_crc_computed else 'NO ✗'}")

# Nintendo logo check
logo_crc_stored = struct.unpack_from('<H', orig_data, 0x15C)[0]
logo_data = orig_data[0xC0:0x15C]
logo_crc_computed = crc16(logo_data)
print(f"  Logo CRC stored:     0x{logo_crc_stored:04X}")
print(f"  Logo CRC computed:   0x{logo_crc_computed:04X}")
print(f"  Logo CRC valid:      {'YES ✓' if logo_crc_stored == logo_crc_computed else 'NO ✗'}")

# Parse FAT
fat_offset = struct.unpack_from('<I', orig_data, 0x48)[0]
fat_len = struct.unpack_from('<I', orig_data, 0x4C)[0]
cpk_start, cpk_end = struct.unpack_from('<II', orig_data, fat_offset)
sdat_start, sdat_end = struct.unpack_from('<II', orig_data, fat_offset + 8)
cpk_size = cpk_end - cpk_start
sdat_size = sdat_end - sdat_start

print(f"\n  data.cpk:      offset=0x{cpk_start:X}, size={cpk_size:,}")
print(f"  sound_data:    offset=0x{sdat_start:X}, size={sdat_size:,}")

print(f"\n{'=' * 60}")
print("STEP 2: Backup original ROM")
print("=" * 60)

if not os.path.exists(BACKUP_ROM):
    shutil.copy2(ORIG_ROM, BACKUP_ROM)
    print(f"  Backed up to: {BACKUP_ROM}")
else:
    # Verify backup matches
    with open(BACKUP_ROM, 'rb') as f:
        backup_md5 = hashlib.md5(f.read()).hexdigest()
    if backup_md5 == md5:
        print(f"  Backup already exists and matches original ✓")
    else:
        print(f"  WARNING: Backup exists but differs! Re-backing up...")
        shutil.copy2(ORIG_ROM, BACKUP_ROM)

print(f"\n{'=' * 60}")
print("STEP 3: Compare CPK structures")
print("=" * 60)

# Extract original CPK header from ROM
orig_cpk = orig_data[cpk_start:cpk_end]

# Read new CPK
with open(NEW_CPK, 'rb') as f:
    new_cpk = f.read()

print(f"  Original CPK size: {len(orig_cpk):,}")
print(f"  New CPK size:      {len(new_cpk):,}")
print(f"  Difference:        {len(new_cpk) - len(orig_cpk):+,}")

# Compare CPK magic and header
print(f"\n  Original CPK magic: {orig_cpk[:4]}")
print(f"  New CPK magic:      {new_cpk[:4]}")

# Parse @UTF header from both CPKs
def parse_cpk_header(cpk_data, label):
    """Parse the CPK header's @UTF table to extract key metadata fields."""
    magic = cpk_data[0:4]
    if magic != b'CPK ':
        print(f"  [{label}] ERROR: Not a CPK file! Magic: {magic}")
        return None
    
    # Read CPK header packet
    # After 'CPK ' there's 0xFF000000 (flag), then the @UTF table offset info
    utf_offset = 0x10  # @UTF table starts at offset 16 in the CPK
    utf_magic = cpk_data[utf_offset:utf_offset+4]
    print(f"  [{label}] UTF magic at 0x{utf_offset:X}: {utf_magic}")
    
    # Check first 64 bytes hex
    print(f"  [{label}] First 64 bytes: {cpk_data[:64].hex()}")
    
    return True

print("\n--- Original CPK Header ---")
parse_cpk_header(orig_cpk, "ORIG")

print("\n--- New CPK Header ---") 
parse_cpk_header(new_cpk, "NEW")

# Compare first 2048 bytes (CPK header region before content)
header_match = orig_cpk[:2048] == new_cpk[:2048]
print(f"\n  CPK header (first 2048 bytes) identical: {'YES ✓' if header_match else 'NO ✗'}")

if not header_match:
    print("  Differences in CPK header:")
    for i in range(min(2048, len(orig_cpk), len(new_cpk))):
        if orig_cpk[i] != new_cpk[i]:
            print(f"    Offset 0x{i:04X}: orig=0x{orig_cpk[i]:02X} new=0x{new_cpk[i]:02X}")

# Check ITOC location - it's stored in the CPK header @UTF table
# Let's find the ItocOffset field
# The CPK @UTF table has fields like ContentOffset, ItocOffset, etc.
# We can search for the ITOC magic "ITOC" in both files
def find_itoc(cpk_data, label):
    pos = cpk_data.find(b'ITOC')
    if pos >= 0:
        print(f"  [{label}] ITOC found at offset 0x{pos:X}")
        # Read some bytes around ITOC
        print(f"  [{label}] ITOC region: {cpk_data[pos:pos+32].hex()}")
        return pos
    else:
        print(f"  [{label}] ITOC NOT FOUND!")
        return None

print("\n--- ITOC Location ---")
orig_itoc_pos = find_itoc(orig_cpk, "ORIG")
new_itoc_pos = find_itoc(new_cpk, "NEW")

if orig_itoc_pos and new_itoc_pos:
    # Compare ITOC tables
    orig_itoc_region = orig_cpk[orig_itoc_pos:orig_itoc_pos+256]
    new_itoc_region = new_cpk[new_itoc_pos:new_itoc_pos+256]
    if orig_itoc_region == new_itoc_region:
        print("  ITOC header (first 256 bytes) identical: YES ✓")
    else:
        print("  ITOC header differs!")
        for i in range(256):
            if orig_itoc_region[i] != new_itoc_region[i]:
                print(f"    ITOC+0x{i:04X}: orig=0x{orig_itoc_region[i]:02X} new=0x{new_itoc_region[i]:02X}")

print(f"\n{'=' * 60}")
print("STEP 4: Quick file content spot-check") 
print("=" * 60)

# Check first file content at ContentOffset=2048 in both CPKs
print(f"  Original CPK content at offset 2048: {orig_cpk[2048:2080].hex()}")
print(f"  New CPK content at offset 2048:      {new_cpk[2048:2080].hex()}")

# Count how many 512-byte-aligned regions differ
diff_regions = 0
check_len = min(len(orig_cpk), len(new_cpk))
for off in range(0, check_len, 512):
    end = min(off + 512, check_len)
    if orig_cpk[off:end] != new_cpk[off:end]:
        diff_regions += 1

print(f"\n  Total 512-byte regions compared: {check_len // 512}")
print(f"  Regions that differ: {diff_regions}")

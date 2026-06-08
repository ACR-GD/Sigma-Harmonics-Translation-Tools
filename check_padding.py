#!/usr/bin/env python3
"""
Diagnostic: check sizes of definitive build to see if we can use padding.
"""
import sys

# In definitive build: Final CPK size: 121,378,872
final_cpk_size = 121378872
itoc_size = 53816
orig_itoc_offset = 0x73D4000 # 121454592
orig_cpk_size = 121508408

new_content_size = final_cpk_size - itoc_size
print(f"New content size (without ITOC): {new_content_size:,} bytes")
print(f"Original ITOC offset:          {orig_itoc_offset:,} bytes")

if new_content_size <= orig_itoc_offset:
    print(f"We can pad! We need {orig_itoc_offset - new_content_size:,} bytes of padding.")
else:
    print(f"We CANNOT pad. New content is too large by {new_content_size - orig_itoc_offset:,} bytes.")

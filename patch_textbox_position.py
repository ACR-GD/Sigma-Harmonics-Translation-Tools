#!/usr/bin/env python3
"""
Sigma Harmonics - Step 1 Patch: Move Dialog Text Box to Bottom of Screen
=========================================================================
Patches arm9.bin to relocate the vertical right-side text box to a
horizontal bottom-of-screen position.

WHAT WE KNOW (from pyghidra decompilation):
============================================
FUN_02046d38 (MesText_clearTilemap) draws the textbox border:
  - Calls FUN_02011944(left, left_end, mode, n) → left tile column
  - Calls FUN_02011944(right, right_end, mode, n) → right tile column
  - Calls FUN_02011944(top, top_end, mode, n) → top tile row
  - Calls FUN_02011944(bottom, bot_end, mode, n) → bottom tile row
  - Then calls FUN_02046b28(this, tilemap, left, top, width, height)

FUN_02011944 = lerp(start, end, mode, divisor):
  Returns start + mode*(end-start)/divisor
  When mode=0 → returns start (the "default" position)

Current textbox (vertical, right side of screen):
  left   = 16 tiles (col 16 = pixel 128)   start=16, end=7
  right  = 19 tiles (col 19 = pixel 152)   start=19, end=30
  top    = 3  tiles (row 3  = pixel 24)    start=3,  end=3
  bottom = 4  tiles (row 4  = pixel 32)    start=4,  end=11
  → Box is 4 cols wide × 2 rows tall (32×16px in tilemap)
  → BG scroll makes tilemap right-side visible as right edge of screen

FUN_02047148 (MesText_setPosition) sets BG scroll:
  X = -((256 - this->a20) - this->width_tiles * 8)
  Y = -(this->a24)
  → "256 - a20 - width*8" = left screen edge of the box in pixels

TARGET: Left-side vertical strip → horizontal bar at book bottom (left)
  - DS cols 1..11 = pixels 8..88 (left side of DS screen)
  - DS rows 0..23 = full height (full book page width)
  → In book mode (CCW rotation): 192px wide × 80px tall bar at book top/left ✓

PATCH STRATEGY:
  1. Change the 4 coordinate MOVs in FUN_02046d38
  2. Change the BG scroll in FUN_02047148 to position at bottom-center

Usage:
    python3 patch_textbox_position.py [--dry-run] [--output patched_arm9.bin]
"""

import argparse
import struct
import shutil
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ARM9_IN  = Path("ghidra_workspace/arm9.bin")
ARM9_OUT = Path("ghidra_workspace/arm9_step1.bin")
BASE     = 0x02000000

def ram_to_off(a): return a - BASE
def u32(data, a):  return struct.unpack_from("<I", data, ram_to_off(a))[0]

# ── ARM32 encoding helpers ────────────────────────────────────────────────────

def arm_mov_imm(rd, imm8):
    """Encode ARM32 MOV Rd, #imm8 (no shift, imm must fit in 8 bits)."""
    assert 0 <= imm8 <= 255, f"imm8 {imm8} out of range"
    # E3A0_d_0_imm  (cond=AL, S=0, Rd, rot=0, imm8)
    return 0xE3A00000 | (rd << 12) | imm8

def arm_b(from_addr, to_addr):
    """Encode ARM32 B (branch, not link)."""
    offset = (to_addr - from_addr - 8) >> 2
    return 0xEA000000 | (offset & 0x00FFFFFF)

def arm_nop():
    """ARM32 NOP (MOV r0, r0)."""
    return 0xE1A00000

def pack32(val):
    return struct.pack("<I", val)

# ── Patch definitions ─────────────────────────────────────────────────────────

# ── Book-mode orientation explanation ─────────────────────────────────────────
# The DS is held sideways like a book (rotated 90° CLOCKWISE so right side faces up):
#   DS right (x=255) = book TOP
#   DS left  (x=0)   = book BOTTOM
#   DS top   (y=0)   = book LEFT edge of page
#   DS bottom (y=191) = book RIGHT edge of page
#
# For a text box at BOTTOM of book page (below character portrait):
#   → Needs to be at the DS RIGHT side in normal orientation
#   → A VERTICAL STRIP in DS view = HORIZONTAL BAR in book view ✓
#
# For English text reading LEFT→RIGHT in book mode:
#   Book left→right = DS top→bottom (y direction) → Step 2 will handle this

# Target layout: vertical strip on DS right side = horizontal bar at book bottom
# NDS screen: 256×192px, tilemap 32×24 tiles (8px each)
# Box goal: DS cols 20..30, DS rows 0..23
#   → DS view: 88px wide × 192px tall strip at right of screen
#   → Book view: 192px wide × 88px tall bar at BOTTOM of page  ✓

BOX_LEFT   = 1   # tile col 1  = DS pixel 8   (left side of DS screen)
BOX_RIGHT  = 11  # tile col 11 = DS pixel 88  (left quarter of DS screen)
BOX_TOP    = 0   # tile row 0  = DS pixel 0   (full DS height = full book width)
BOX_BOTTOM = 23  # tile row 23 = DS pixel 184 (near DS bottom edge)

# Animation end values (lerp target) — keep same as start (no animation)
BOX_LEFT_END   = 1
BOX_RIGHT_END  = 11
BOX_TOP_END    = 0
BOX_BOTTOM_END = 23

# BG scroll: HOFS=0, VOFS=0 so tilemap col N appears at screen pixel N*8
# (tilemap col 20 → screen pixel 160, no extra offset needed)
SCROLL_HOFS = 0   # pixels to offset horizontally (0 = direct mapping)
SCROLL_VOFS = 0   # pixels to offset vertically

# r0=0, r1=1 (register encoding)
R0, R1 = 0, 1

PATCHES = {
    # ── FUN_02046d38 textbox border tile coordinates ──────────────────────────
    # Call 1 — left column start
    0x2046DBC: (arm_mov_imm(R0, BOX_LEFT),       f"left_col  start: tile {BOX_LEFT} = DS px {BOX_LEFT*8}"),
    # Call 1 — left column end (keep same = no animation)
    0x2046DC4: (arm_mov_imm(R1, BOX_LEFT_END),   f"left_col  end:   tile {BOX_LEFT_END}"),

    # Call 2 — right column start
    0x2046DE0: (arm_mov_imm(R0, BOX_RIGHT),       f"right_col start: tile {BOX_RIGHT} = DS px {BOX_RIGHT*8}"),
    # Call 2 — right column end
    0x2046DE8: (arm_mov_imm(R1, BOX_RIGHT_END),   f"right_col end:   tile {BOX_RIGHT_END}"),

    # Call 3 — top row start
    0x2046E0C: (arm_mov_imm(R0, BOX_TOP),         f"top_row   start: tile {BOX_TOP} = DS px {BOX_TOP*8}"),
    # Call 3 — top row end (was MOV r1,r0 — change to MOV r1,#imm)
    0x2046E14: (arm_mov_imm(R1, BOX_TOP_END),     f"top_row   end:   tile {BOX_TOP_END} [was MOV r1,r0]"),

    # Call 4 — bottom row start
    0x2046E3C: (arm_mov_imm(R0, BOX_BOTTOM),       f"bot_row   start: tile {BOX_BOTTOM} = DS px {BOX_BOTTOM*8}"),
    # Call 4 — bottom row end
    0x2046E44: (arm_mov_imm(R1, BOX_BOTTOM_END),   f"bot_row   end:   tile {BOX_BOTTOM_END}"),

    # ── FUN_02047148 BG scroll — patch else-branch to use HOFS=0, VOFS=0 ──────
    # We replace the 10-instruction else-branch at 0x20471c0..0x20471e7 with:
    #   LDR r0,[r4,#0xc]   ; bg layer id
    #   LDR r1,[r4,#0x10]  ; bg sublayer
    #   MOV r2, #0         ; HOFS = 0 (negate = 0)
    #   MOV r3, #0         ; VOFS = 0 (negate = 0)
    #   BL  SetBGScroll    ; SetBGScroll(layer, sublayer, 0, 0)
    #   B   0x20471e8      ; continue
    #   NOP × 4
    # With HOFS=0: tilemap col 20 → screen pixel 160 (DS right area = book bottom)
    # With VOFS=0: tilemap row 0..23 → screen pixel 0..184 (full height = full book width)
}

SCROLL_PATCH_BASE = 0x20471c0

def make_scroll_patch():
    """
    Replace the 10-instruction else-branch of FUN_02047148 (0x20471c0..0x20471e7).
    Sets BG scroll to HOFS=0, VOFS=0 so tilemap coords map directly to screen pixels.
    With HOFS=0: tilemap col 20 → screen pixel 160 (DS right side = book bottom) ✓
    With VOFS=0: full height visible (full book page width) ✓
    """
    instrs = []
    # r4 = 'this' pointer (preserved from function prologue)
    instrs.append(0xE5940000 | (0 << 12) | 0x00C)   # LDR r0, [r4, #0xc]  — bg layer id
    instrs.append(0xE5940000 | (1 << 12) | 0x010)   # LDR r1, [r4, #0x10] — bg sublayer
    instrs.append(arm_mov_imm(2, 0))                  # MOV r2, #0  (HOFS=0, negated = 0)
    instrs.append(arm_mov_imm(3, 0))                  # MOV r3, #0  (VOFS=0, negated = 0)
    bl_target = 0x200e090
    bl_from   = SCROLL_PATCH_BASE + len(instrs) * 4
    instrs.append(0xEB000000 | (((bl_target - bl_from - 8) >> 2) & 0x00FFFFFF))  # BL SetBGScroll
    b_from = SCROLL_PATCH_BASE + len(instrs) * 4
    instrs.append(arm_b(b_from, 0x20471e8))          # B 0x20471e8 (rejoin)
    while len(instrs) < 10:
        instrs.append(arm_nop())                       # NOP padding
    return instrs[:10]

# ── Apply patches ─────────────────────────────────────────────────────────────

def apply_patches(data: bytearray, patches: dict, dry_run: bool) -> bytearray:
    print("\n=== Applying coordinate patches to FUN_02046d38 ===")
    for addr, (new_val, desc) in sorted(patches.items()):
        off = ram_to_off(addr)
        old_val = struct.unpack_from("<I", data, off)[0]
        old_imm = old_val & 0xFF
        new_imm = new_val & 0xFF
        print(f"  {hex(addr)}: {hex(old_val)} → {hex(new_val)}  ({desc})")
        if old_val == new_val:
            print(f"           [ALREADY CORRECT — skipping]")
            continue
        if not dry_run:
            struct.pack_into("<I", data, off, new_val)

    print("\n=== Applying BG scroll patch to FUN_02047148 ===")
    scroll_instrs = make_scroll_patch()
    print(f"  Replacing 10 instructions at {hex(SCROLL_PATCH_BASE)}..{hex(SCROLL_PATCH_BASE + 10*4 - 1)}")
    print(f"  HOFS = {BOX_LEFT * 8}px  VOFS = {BOX_TOP * 8}px")
    for i, instr in enumerate(scroll_instrs):
        addr = SCROLL_PATCH_BASE + i * 4
        off  = ram_to_off(addr)
        old  = struct.unpack_from("<I", data, off)[0]
        print(f"  [{i}] {hex(addr)}: {hex(old)} → {hex(instr)}")
        if not dry_run:
            struct.pack_into("<I", data, off, instr)

    return data

def verify_patches(data: bytearray, patches: dict):
    print("\n=== Verification ===")
    ok = True
    for addr, (expected, desc) in sorted(patches.items()):
        off = ram_to_off(addr)
        actual = struct.unpack_from("<I", data, off)[0]
        status = "✓" if actual == expected else "✗"
        if actual != expected:
            ok = False
        print(f"  {status} {hex(addr)}: {hex(actual)} (expected {hex(expected)})  [{desc}]")
    return ok

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true", help="Print patches without writing")
    parser.add_argument("--output",   default=str(ARM9_OUT), help="Output file path")
    parser.add_argument("--verify",   action="store_true",   help="Only verify, do not patch")
    args = parser.parse_args()

    if not ARM9_IN.exists():
        print(f"ERROR: {ARM9_IN} not found. Run from sigma-harmonics dir.")
        raise SystemExit(1)

    data = bytearray(ARM9_IN.read_bytes())
    print(f"Loaded {ARM9_IN} ({len(data):,} bytes)")

    if args.verify:
        ok = verify_patches(data, PATCHES)
        print("\n" + ("✅ All patches applied" if ok else "❌ Patches NOT applied (original binary)"))
        return

    print(f"\nTarget textbox layout:")
    print(f"  Left:   tile {BOX_LEFT}  = pixel {BOX_LEFT*8}")
    print(f"  Right:  tile {BOX_RIGHT} = pixel {BOX_RIGHT*8}  (width = {(BOX_RIGHT-BOX_LEFT+1)*8}px)")
    print(f"  Top:    tile {BOX_TOP}   = pixel {BOX_TOP*8}")
    print(f"  Bottom: tile {BOX_BOTTOM}= pixel {BOX_BOTTOM*8} (height = {(BOX_BOTTOM-BOX_TOP+1)*8}px)")
    print(f"  BG scroll: X = -{BOX_LEFT*8}px, Y = -{BOX_TOP*8}px")

    data = apply_patches(data, PATCHES, dry_run=args.dry_run)

    if not args.dry_run:
        out_path = Path(args.output)
        out_path.write_bytes(data)
        print(f"\n✅ Patched binary written to {out_path}")
        print(f"   File size: {len(data):,} bytes (unchanged)")
    else:
        print("\n[DRY RUN] No file written.")

if __name__ == "__main__":
    main()

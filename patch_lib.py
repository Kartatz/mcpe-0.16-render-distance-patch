#!/usr/bin/env python3
"""Patch libminecraftpe.so (MCPE 0.16.2, armeabi-v7a) to raise max render distance to NEW_MAX.

Edits:
1. Options::getMaxViewDistanceChunks @ 0x00AE349A: force return of NEW_MAX.
2. Render-distance level table A @ 0x01A93FF0: [8,10,12,14,18,22] -> [2,4,8,16,32,NEW_MAX].
3. Render-distance level table B @ 0x01A94008: same replacement.
"""
import struct, sys

PATH = "libminecraftpe.so"
data = bytearray(open(PATH, "rb").read())

NEW_MAX = 64
NEW_TABLE = [2, 4, 8, 16, 32, NEW_MAX]
assert NEW_TABLE[0] < NEW_MAX <= 255

edits = [
    # (name, offset, expected_bytes, new_bytes)
    (
        "Options::getMaxViewDistanceChunks -> return %d" % NEW_MAX,
        0x00AE349A,
        bytes.fromhex("d0f8bc01" "50f8040c" "7047"),
        # movs r0, #NEW_MAX ; bx lr (70 47) ; padding nops (00 bf)
        bytes([NEW_MAX & 0xFF, 0x20, 0x70, 0x47] + [0x00, 0xbf] * 3),
    ),
    (
        "level table A -> %s" % NEW_TABLE,
        0x01A93FF0,
        struct.pack("<6i", 8, 10, 12, 14, 18, 22),
        struct.pack("<6i", *NEW_TABLE),
    ),
    (
        "level table B -> %s" % NEW_TABLE,
        0x01A94008,
        struct.pack("<6i", 8, 10, 12, 14, 18, 22),
        struct.pack("<6i", *NEW_TABLE),
    ),
]

for name, off, old, new in edits:
    actual = bytes(data[off:off + len(old)])
    if actual != old:
        print(f"ABORT: {name}: bytes mismatch at 0x{off:08x}: "
              f"expected {old.hex()}, found {actual.hex()}")
        sys.exit(1)
    data[off:off + len(new)] = new
    print(f"patched: {name} @ 0x{off:08x}")

open(PATH, "wb").write(data)
print("done ->", PATH)

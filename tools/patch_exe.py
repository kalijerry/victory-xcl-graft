#!/usr/bin/env python3
"""The 8 local exe patches (all "the title takes 0 as a global and int3-asserts").

Reconstructed from the diff between the official exe and the patched one, so it can be
re-applied to a clean `game_scarlett_master.exe` (e.g. after a torrent recheck replaced it).

    python patch_exe.py <official exe> <output exe>

  +0x56E1AB        8A 40 0E            -> 31 C0 90        (a stub returns NULL, unchecked: return false)
  7 x mov dword [0], imm32 (+ cc)    -> 90 ...            (the assert writes into page 0)
"""
import sys

_INS = bytes.fromhex("c7042500000000")  # mov dword [0]

# offset -> (expected original bytes, replacement bytes)
PATCHES = {
    0x56E1AB: (bytes.fromhex("8a400e"), bytes.fromhex("31c090")),
    0x2215035: (_INS + bytes.fromhex("00000000cc"), b"\x90" * 12),
    0x22151A9: (_INS + bytes.fromhex("00000000"), b"\x90" * 11),
    0x23CEA83: (_INS + bytes.fromhex("21d48b4d"), b"\x90" * 11),
    0x258A400: (_INS + bytes.fromhex("4be9f12e"), b"\x90" * 11),
    0x29DFC80: (_INS + bytes.fromhex("e15e794d"), b"\x90" * 11),
    0x390D4C0: (_INS + bytes.fromhex("78e70eb9"), b"\x90" * 11),
    0x402A070: (_INS + bytes.fromhex("88302818"), b"\x90" * 11),
    # a streaming/decompress assert in the anim path (+0x4da6315 below the image base:
    # `cc 31 c0 c3` – debugbreak, then return 0). While anim.rpf pieces are missing the title
    # takes it; NOPping the int3 lets the failing call return NULL instead of dying.
    0x4DA5715: (bytes.fromhex("cc"), bytes.fromhex("90")),
}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    data = bytearray(open(sys.argv[1], "rb").read())
    for at, (want, put) in sorted(PATCHES.items()):
        have = bytes(data[at:at + len(want)])
        if have == put:
            print(f"{at:#x}: already patched")
            continue
        if have != want:
            print(f"{at:#x}: unexpected bytes {have.hex()} (want {want.hex()})")
            return 1
        data[at:at + len(put)] = put
        print(f"{at:#x}: patched")
    open(sys.argv[2], "wb").write(data)
    print(f"written {sys.argv[2]} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

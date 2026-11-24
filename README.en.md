# VIctory ⇄ XCL bridge (victory-xcl-graft)

Gives [VIctory](https://github.com/Marvisak/VIctory) the half it lacks — the RDNA2→DXIL
translation that [XCL](https://github.com/ivall/xcl) covers 100% of — so world shaders are
drawn instead of dropped. VIctory is the base; XCL is only a **translator process**.
The two licences are incompatible (VIctory GPL-3.0-or-later, XCL GPL-2.0-only), so the bridge
runs across a process boundary and hands over through a sidecar directory plus a single JSON
line — no linking.

> State (2026-11-24): **it runs and it is measured, but the image is not correct yet.**
> On a real RTX 3080: distinct translate failures 424 → **45**, 120 shaders taken over by the
> fallback, draws per frame 815 → 1,929; but XCL's DXIL is 10–100x larger than VIctory's own,
> so pipeline creation queues ~320 entries and drops per frame *rise* 561 → 920.
> WARP is the honest scale (steady pacing, XCL compute cannot run there): failures 441 → 65,
> drops per frame 1,533 → 1,289. Why that is:
> [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md).

"the game" below means the newly released Xbox Series title; this repo never spells its name,
and the `gta6` in paths is just the author's working directory.

## Why not "merge the two projects"

* The private CGBJ build is exactly "VIctory base + borrowed XCL work" and it got in game; its
  code is not public;
* VIctory's own contributors are chasing the same 4,003 failures with their own PRs
  (`#953` +230, `#305`/`#539` +520 programs), but nobody bridges the projects;
* so this goes the other way: **don't port rules, borrow translation results** and put each
  project's strength where it is.

## How it works

```
[producer]  xcl.exe dxil <container> <out.dxil>   ← XCL's translator (patches/xcl)
                ↓ one JSON line: stage + the static samplers it needs
[carrier]   tools/fill_xcl_sidecar.py             ← BLAKE3 of each failed container, writes
                ↓ shaders/<xx>/<blake3>.json + .dxil   the sidecar, resumable
[consumer]  VIctory: VICTORY_XCL_SHADERS=<dir>    ← native translator first, sidecar only
                                                    after it failed (patches/victory)
```

A hit creates the root signature for **XCL's ABI** (root UAV `u0..u5` in space 0, static
samplers in space 1) and the draw is no longer dropped. `VICTORY_DUMP_FAILED=<dir>` writes out
every container the title actually used and the translator refused — exactly the producer's
input. With an empty sidecar behaviour is upstream's.

## Quick start

```powershell
# 1. apply the patches (one series per tree)
git clone https://github.com/Marvisak/VIctory; cd VIctory
git apply ../patches/victory/0001-xcl-sidecar-fallback.patch
git apply ../patches/victory/0002-cargo-lock.patch
cargo build --release -p victory

git clone https://github.com/ivall/xcl; cd ../xcl
git apply ../patches/xcl/0001-dxil-producer-command.patch   # and 0002..0006, see below
cargo build --release -p xcl

# 2. one run, so refused containers get dumped
$env:VICTORY_DUMP_FAILED='...\failed'; $env:VICTORY_D3D12_WARP='1'
.\victory.exe run <exe> --execute

# 3. build the sidecar (XCL_DXC_DIR must point at DXC 1.9+)
$env:XCL_DXC_DIR='...\dxc\bin\x64'
python tools\fill_xcl_sidecar.py ...\failed ...\sidecar

# 4. run with the sidecar
$env:VICTORY_XCL_SHADERS='...\sidecar'
```

## Patch list (`patches/xcl`)

| Patch | What | Required |
|---|---|---|
| 0001 | the `xcl dxil` producer command (VS/PS/CS, split form for 32-lane devices) | yes |
| 0002 | package identifier returned into a 33-byte buffer (the title asserts during `System Init` otherwise) | yes |
| 0003 | readers admit writers (`FILE_SHARE_READ\|WRITE\|DELETE`), so it runs while the image is repaired | strongly |
| 0004 | upstream **#1321**: oversized structured code falls back to `pc` blocks (the commit blow-up) | strongly |
| 0005 | upstream **#1273**: a bind no longer waits behind the workers' queue | advised |
| 0006 | `build_is_wanted` drift in the preload path | advised |

`0002` also carries 13 `[api]` warning-level debug lines; drop them if too noisy.

## Still missing, in order

1. **Bindings**: the sidecar now carries `user_data` (dword indexes the program reads) and `reads_res`/`reads_mem`, but `slot`/`kind` and the actual `u1`/`u2..u5` bindings are not wired yet; `user_data`, `u1 res` and the `u2..u5 mem`
   windows are empty, so today only "not dropped, binds" holds — initial SGPRs and address
   reads come back 0 and scene elements are missing. XCL has to report which user-data dwords a
   program reads, which `u` register an address term comes from, and which root parameter that
   maps to.
2. **Compile backlog from huge DXIL**: precompile sidecar pipelines offline (XCL's `pipelines`
   plus its driver-blob cache is the proven shape) and cap the `make` workers.
3. **MS/GS containers** (746 of the failures) need the two-pass pipeline; `xcl dxil` refuses them.
4. One 4.8 s submission during world load trips a driver TDR.

## Data prerequisite (important)

The leaked image is incomplete: **76 of 13,345 pieces bad, 1.19 GiB**, including a 16 MiB zero
hole in `anim.rpf`; both projects die on the same `int3` at `+0x4da6315`. How to detect and
repair it, the `fastresume` bitfield trap and the sharing-handle trap: [docs/DATA.md](docs/DATA.md).

## Licence

The bridge glue: GPL-3.0-or-later (like VIctory). `patches/xcl` apply to GPL-2.0-only XCL; each
side keeps its own licence and they only meet at run time through a process + JSON.
No game data in this repository.

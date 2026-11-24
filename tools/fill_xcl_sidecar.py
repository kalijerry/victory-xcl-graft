#!/usr/bin/env python3
"""Fill VIctory's XCL sidecar for shaders its own emitter refuses.

Input: a folder of dumped console shader containers (one file per shader). For each, the
container's BLAKE3 is computed (the same key VIctory's shader cache uses: full 64 hex, mirror
of the `cache\\shaders\\<xx>\\<hash>` layout), the shader is translated with XCL
(`xcl dxil <in> <out.dxil>`) and a sidecar entry is written:

    <out>/shaders/<xx>/<blake3>.json   {"stage":"ps","dxil":"<abs path>","samplers":[[..,cmp]]}
    <out>/shaders/<xx>/<blake3>.dxil   the DXIL bytes

Existing entries are skipped, so the run is resumable. Failures are counted per reason and
reported; they are exactly the shaders neither emitter covers.

    python fill_xcl_sidecar.py <dump-dir> <sidecar-out-dir> [--limit N]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import blake3

GTA6 = r"C:\Users\z7299\Documents\deepseek-harness\default-workspace\gta6"
XCL = os.path.join(GTA6, "xcl", "target", "release", "xcl.exe")
DXC = os.path.join(GTA6, "dxc", "bin", "x64")


def one(container: str, out_root: str) -> tuple[bool, str]:
    data = open(container, "rb").read()
    key = blake3.blake3(data).hexdigest()
    sub = os.path.join(out_root, "shaders", key[:2])
    side = os.path.join(sub, key + ".json")
    if os.path.exists(side):
        return True, "skip"
    os.makedirs(sub, exist_ok=True)
    dxil = os.path.join(sub, key + ".dxil")
    env = dict(os.environ, XCL_DXC_DIR=DXC, XCL_NETWORK="0")
    r = subprocess.run([XCL, "dxil", container, dxil], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        try:
            os.remove(dxil)
        except OSError:
            pass
        why = (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"exit {r.returncode}"
        why = re.sub(r"^.*?: ", "", why)[:120]
        return False, why
    try:
        line = [l for l in r.stdout.splitlines() if l.startswith("{")][-1]
        info = json.loads(line)
    except (IndexError, json.JSONDecodeError):
        return False, "no json from xcl dxil"
    info["dxil_file"] = os.path.basename(dxil)
    info["bytes"] = os.path.getsize(dxil)
    with open(side + ".tmp", "w") as f:
        json.dump(info, f)
    os.replace(side + ".tmp", side)
    return True, info["stage"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=10**9)
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    files = [
        os.path.join(dp, f)
        for dp, _, fs in os.walk(a.dump)
        for f in fs
        if os.path.getsize(os.path.join(dp, f)) > 64
    ][: a.limit]
    print(f"{len(files)} containers from {a.dump}")
    made = failed = skipped = 0
    reasons: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for ok, why in ex.map(lambda c: one(c, a.out), files):
            if ok:
                if why == "skip":
                    skipped += 1
                else:
                    made += 1
            else:
                failed += 1
                reasons[why] = reasons.get(why, 0) + 1
            n = made + failed + skipped
            if n % 50 == 0:
                print(f"  {n}/{len(files)}: made {made}, failed {failed}, skipped {skipped}")
    print(f"done: made {made}, failed {failed}, skipped {skipped}, out {a.out}")
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {n:5d}x {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

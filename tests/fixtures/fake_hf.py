#!/usr/bin/env python3
"""Fake 'hf download' used ONLY by hermetic e2e tests of the stall-watch (issue #55).

This is a real, runnable subprocess that mimics `hf download --local-dir <dest>` by
writing bytes into the destination's `.cache/<etag>.incomplete` file (which is
exactly what the real hf CLI does and what `tree_bytes` in hf_download.py counts).

Modes (driven by env):
  FAKE_HF_MODE=grow   -> appends chunks continuously (healthy download)
  FAKE_HF_MODE=stall  -> writes a little then sits forever at 0 bytes (dead connection)
  FAKE_HF_MODE=exit0  -> writes the full final file and exits 0 (done)  [unused here]
  FAKE_HF_MODE=throttle-once     -> answers a Hub 429 once, then downloads (issue #385)
  FAKE_HF_MODE=throttle-forever  -> answers a Hub 429 every time (issue #385)
  FAKE_HF_MODE=snapshot          -> writes a whole-repo snapshot (no filename given)

Run as: python fake_hf.py download <repo> <file> --local-dir <dest> --max-workers N
"""
import os, sys, time

#: What the real CLI prints when the Hub rate-limits it (measured, issue #385). The
#: seconds are small on purpose: a test asserts the downloader waits the Hub's number,
#: and the wait is REAL wall-clock sleep.
THROTTLE = ("Error: Local entry not found.\n"
            "429 Too Many Requests: you have reached your 'api' rate limit.\n"
            "Retry after 2 seconds (0/1000 requests remaining in current 300s window).\n")

def _dest(args):
    # args look like: download repo file --local-dir DEST --max-workers 4
    for i, a in enumerate(args):
        if a == "--local-dir":
            return args[i + 1]
    return "."

def main():
    mode = os.environ.get("FAKE_HF_MODE", "grow")
    dest = _dest(sys.argv[1:])
    cache = os.path.join(dest, ".cache")
    os.makedirs(cache, exist_ok=True)
    partial = os.path.join(cache, "759fd9a.incomplete")  # any etag name
    if mode == "grow":
        # healthy: append steadily for a while, then place the final file and exit 0
        t_end = time.time() + 4
        with open(partial, "wb") as f:
            while time.time() < t_end:
                f.write(b"\x00" * 65536)
                f.flush()
                time.sleep(0.05)
        # place the final file so hf_download's `rc==0 and exists(final_path)` is satisfied
        with open(os.path.join(dest, "model.gguf"), "wb") as f:
            f.write(b"\x00" * 131072)
        return 0
    elif mode == "stall":
        # write a little, then hang (0 extra bytes) forever — simulates a dead connection
        with open(partial, "wb") as f:
            f.write(b"\x00" * 65536)
            f.flush()
        time.sleep(3600)  # never advances; the stall-watch must kill us
        return 0
    elif mode == "xet-stall":
        # issue #105: hf-xet makes no progress; plain HTTP (HF_HUB_DISABLE_XET=1) works
        if os.environ.get("HF_HUB_DISABLE_XET") == "1":
            os.environ["FAKE_HF_MODE"] = "grow"
            return main()
        time.sleep(3600)
        return 0
    elif mode == "exit0":
        full = os.path.join(dest, "model.gguf")
        with open(full, "wb") as f:
            f.write(b"\x00" * 131072)
        return 0
    elif mode == "snapshot":
        # a whole-repo download: no filename argument, several real files in dest
        with open(os.path.join(dest, "config.json"), "wb") as f:
            f.write(b"{}")
        with open(os.path.join(dest, "model.safetensors"), "wb") as f:
            f.write(b"\x00" * 4096)
        return 0
    elif mode in ("throttle-once", "throttle-forever"):
        # The Hub throttles this token. `throttle-once` succeeds on the NEXT invocation
        # of this fake, so the downloader's retry is proven to have worked.
        seen = os.path.join(dest, ".throttle-calls")
        calls = int(open(seen).read()) if os.path.exists(seen) else 0
        with open(seen, "w") as f:
            f.write(str(calls + 1))
        if mode == "throttle-forever" or calls == 0:
            sys.stdout.write(THROTTLE)
            sys.stdout.flush()
            return 1
        full = os.path.join(dest, "model.gguf")
        with open(full, "wb") as f:
            f.write(b"\x00" * 131072)
        return 0
    return 0

if __name__ == "__main__":
    sys.exit(main())

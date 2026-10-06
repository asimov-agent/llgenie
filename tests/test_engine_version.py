"""Engine image binary version check (host-side; docker is required).

Run after `make install` / `make build-engine` for every built engine image,
skipping the Metal/Apple-Silicon-only variant. Requires docker: it launches the
image and asserts the entrypoint `version` (alias of detect) reports text. This
is the "at least --version works" guarantee for engines that cannot serve on the
current host (e.g. GPU images on a GPU-less runner).

    LLGENIE_TEST_ENGINE=llama.cpp LLGENIE_TEST_ARCH=cpu \
        python3 -m pytest tests/test_engine_version.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_image as ei  # noqa: E402


def test_engine_binary_reports_a_version():
    engine = os.environ.get("LLGENIE_TEST_ENGINE", "")
    arch = os.environ.get("LLGENIE_TEST_ARCH", "")
    if not (engine and arch):
        pytest.fail("LLGENIE_TEST_ENGINE/LLGENIE_TEST_ARCH are not set: run through "
                    "`make test-engine-image ENGINE=<id> ARCH=<arch>`")

    spec = ei.resolve(engine, None, arch)
    r = subprocess.run([ei.RUNTIME, "run", "--rm", spec["tag"], "version"],
                       capture_output=True, text=True, timeout=300)
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == 0, f"{engine}/{arch} `version` exited {r.returncode}: {out}"
    assert out, f"{engine}/{arch} `version` printed nothing"
    print(f"[version] {engine}/{arch}: {out.splitlines()[-1]}")


def test_strata_engine_runs_on_avx2_cpus_and_setup_reuses_it():
    """Strata only: the engine compiled into the image must run on an AVX2 CPU without
    AVX-512 (Intel 12th-14th gen, the RTX 4090 laptop it crashed on). Built with ggml's
    -march=native on an AVX-512 CI runner, ggml_cpu_init (run at every start, before any
    runtime dispatch) held a zmm instruction: SIGILL at start. STRATA_PORTABLE=ON (Strata's
    own release build) pins ggml to AVX2. The image must also carry engine/BUILD.json in
    the form setup.py writes, so setup reuses the engine instead of recompiling it (with
    -march=native, on the user's CPU) at every container start."""
    engine = os.environ.get("LLGENIE_TEST_ENGINE", "")
    arch = os.environ.get("LLGENIE_TEST_ARCH", "")
    if engine != "strata":
        print(f"[portable] {engine or '-'}/{arch or '-'}: not Strata, nothing to check")
        return
    spec = ei.resolve(engine, None, arch)
    src = "/opt/llgenie/engines/strata/src"
    script = (f"cd {src} && cat engine/BUILD.json && echo '---' && "
              "objdump -d --no-show-raw-insn engine/strata --disassemble=ggml_cpu_init | grep -c zmm || true")
    r = subprocess.run([ei.RUNTIME, "run", "--rm", "--entrypoint", "bash", spec["tag"], "-c", script],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    meta_txt, zmm = r.stdout.rsplit("---", 1)
    import json
    meta = json.loads(meta_txt)
    assert meta["source"] == "local" and meta.get("src"), meta
    assert int(zmm.strip() or 0) == 0, f"{engine}/{arch}: ggml_cpu_init uses AVX-512 (zmm): SIGILL on AVX2 CPUs"
    # setup.py's own check accepts the shipped engine (no recompile)
    check = (f"cd {src} && py/bin/python -c 'import json,setup; m=json.load(open(\"engine/BUILD.json\")); "
             "print(m[\"src\"] == setup.source_hash(setup.ENGINE_SOURCES))'")
    r = subprocess.run([ei.RUNTIME, "run", "--rm", "--entrypoint", "bash", spec["tag"], "-c", check],
                       capture_output=True, text=True, timeout=300)
    assert r.stdout.strip().splitlines()[-1] == "True", r.stdout + r.stderr
    print(f"[portable] strata/{arch}: no AVX-512 in ggml_cpu_init, BUILD.json matches setup.py")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

#!/usr/bin/env bash
# Probe how `rocm` resolves in a throwaway container from the engine base image,
# WITH and WITHOUT the AMD wheel index. Proves the --no-build-isolation -e . step
# will either fall back to the PyPI rocm==0.1.0 sdist (needs poetry, dies) or
# resolve the prebuilt rocm==7.14.x wheel (clean) — without a 4h build.
#
#   ./probe_rocm_resolution.sh llgenie/base-rocm:<tag>
#
# Exit 0 always: this is a REPORT, not a gate. Read the two `+ rocm==` lines.
set -uo pipefail
BASE="${1:?usage: $0 <base-image>}"

run() {
  docker run --rm "$BASE" bash -lc "export PATH=/opt/llgenie/bin:\$PATH; $1" 2>&1 | tail -12
}

echo "== WITHOUT the AMD index (what a bare '-e .' resolves; PyPI placeholder if 0.1.0):"
run "uv pip install --dry-run --system --break-system-packages rocm --index-strategy unsafe-best-match"

echo
echo "== WITH the AMD index (the fix; expect rocm==7.14.x prebuilt wheel):"
run "uv pip install --dry-run --system --break-system-packages rocm --extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match"

echo
echo "Verdict: if the first shows 'rocm==0.1.0' and the second shows 'rocm==7.14', the cell fails"
echo "on a missing '-e .' AMD index, NOT on torch and NOT on a timeout."

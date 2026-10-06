#!/usr/bin/env bash
# build_llama_server.sh <tree> <backend>
#
# Clone-or-pull the right llama.cpp tree to its latest commit and build it for
# the given backend. This is the single code path for BOTH the host
# (`make install` -> auto-detected variant) and CI (parallel per-variant jobs).
#
#   tree    : prism | upstream
#   backend : metal | cuda | cpu
#
# Guarantees:
#   * clone-or-pull then build — never a stale prebuilt (clone if absent,
#     fetch+reset to the tree branch tip if present);
#   * the build is done in a per-backend dir (build-cpu / build-cuda /
#     build-metal) so parallel variants never collide;
#   * the binary is verified to exist and respond to --help (exit 0).
#
# Exit codes: 0 = built + verified, 1 = failure (loud; never a skip).
set -euo pipefail

TREE="${1:-prism}"
BACKEND="${2:-cpu}"
REPO_ROOT="${REPO_ROOT:-$PWD/..}"          # this repo (Makefile passes REPO=$PWD)
SERVER_ROOT="${SERVER_ROOT:-$HOME/repository/git}"

# Resolve repo url, branch, clone dir, build dir and cmake flags from the
# GENERATED params (containers/engines/params/<id>.json, written from the
# engine skill by `make generate-engine-params`). This build never reads a
# skill and needs no LLM. Hardware-derived flags (CMAKE_CUDA_ARCHITECTURES from
# nvidia-smi compute_cap, GPU_TARGETS from rocminfo) are added only when the
# hardware is visible, so a GPU-less CI container gets CMake's default list.
# The params keep GGML_NATIVE=OFF: the CI build cache restores binaries onto a
# DIFFERENT runner, and a -march=native binary crashes with SIGILL there.
case "$TREE" in
  prism)    SKILL_ID="llama.cpp-prism" ;;
  upstream) SKILL_ID="llama.cpp" ;;
  *)        SKILL_ID="$TREE" ;;
esac
ENV_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/native_build_env.py"
BUILD_ENV="$(SERVER_ROOT="$SERVER_ROOT" python3 "$ENV_PY" "$SKILL_ID" "$BACKEND")" \
  || { echo "[FAIL] no generated $BACKEND build params for $SKILL_ID (run make generate-engine-params)"; exit 1; }
eval "$BUILD_ENV"
echo "[build] tree=$TREE params=containers/engines/params/$SKILL_ID.json ($REPO_URL, branch=$BRANCH) at $TREE_DIR"

echo "[build] backend=$BACKEND build-dir=$BUILD_DIR"
echo "[build] cmake flags (from generated params + detected hardware): $CMAKE_FLAGS"

# --- toolchain preflight (loud failure, never a skip) ---------------------
for tool in git cmake g++; do
  command -v "$tool" >/dev/null 2>&1 || { echo "[FAIL] required tool '$tool' not on PATH"; exit 1; }
done
if [[ "$BACKEND" == "cuda" ]]; then
  NVCC="${NVCC:-nvcc}"
  if ! command -v "$NVCC" >/dev/null 2>&1; then
    for p in /opt/cuda/bin/nvcc /usr/local/cuda/bin/nvcc; do
      [[ -x "$p" ]] && NVCC="$p"
    done
  fi
  command -v "$NVCC" >/dev/null 2>&1 || { echo "[FAIL] nvcc not found. The CUDA toolkit must already be in the image (nvidia/cuda). This script only compiles llama-server."; exit 1; }
  echo "[build] prebuilt CUDA toolkit: $NVCC ($(nvcc --version | tail -1 2>/dev/null || true))"
  echo "[build] compiling llama-server against that toolkit"
fi
if [[ "$BACKEND" == "metal" && "$(uname -s)" != "Darwin" ]]; then
  echo "[FAIL] metal requires macOS (uname -s != Darwin). Cannot build a Metal backend here." >&2
  exit 1
fi

# --- clone-or-pull to the latest commit -----------------------------------
if [[ -d "$TREE_DIR/.git" ]]; then
  echo "[build] $TREE_DIR already exists -> fetching latest of branch $BRANCH"
  # The CI cache is restored as the runner user and used inside a root
  # container. Git refuses that as "dubious ownership" unless the path is safe.
  git config --global --add safe.directory "$TREE_DIR"
  git -C "$TREE_DIR" fetch origin "$BRANCH"
  # Reset the working tree to the remote tip (clone-or-pull, always current).
  # We do NOT `git clean -fd` (which would delete the untracked build dirs) —
  # cmake re-compiles whatever the current tip requires, so builds stay incremental.
  git -C "$TREE_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
  HEAD_COMMIT="$(git -C "$TREE_DIR" rev-parse --short HEAD)"
else
  echo "[build] cloning $TREE_DIR from $REPO_URL (branch $BRANCH)"
  git clone -b "$BRANCH" "$REPO_URL" "$TREE_DIR"
  HEAD_COMMIT="$(git -C "$TREE_DIR" rev-parse --short HEAD)"
fi
echo "[build] HEAD @ $HEAD_COMMIT (always synced to latest commit)"

# --- build (per-backend dir so parallel variants never collide) ------------
mkdir -p "$BUILD_DIR"
# Line-buffer cmake/nvcc so every variant's compile shows up in the CI log
# as it runs, instead of in one chunk at the end. macOS Homebrew coreutils
# names the tool gstdbuf.
if command -v stdbuf >/dev/null 2>&1; then
  LINEBUF=(stdbuf -oL -eL)
elif command -v gstdbuf >/dev/null 2>&1; then
  LINEBUF=(gstdbuf -oL -eL)
else
  LINEBUF=()
fi
if [[ -d "$BUILD_DIR" ]]; then
  echo "[build] reusing existing build dir $BUILD_DIR"
else
  echo "[build] no existing build dir; compiling from scratch into $BUILD_DIR"
fi
echo "[build] configuring: cmake -S $TREE_DIR -B $BUILD_DIR -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS"
"${LINEBUF[@]}" cmake -S "$TREE_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS
echo "[build] building llama-server (this is the slow part)"
# All online cores. CI passes BUILD_JOBS from the runner so a container
# cgroup cannot shrink the job count. macOS has no nproc; sysctl does.
if [[ -n "${BUILD_JOBS:-}" && "${BUILD_JOBS}" =~ ^[0-9]+$ && "${BUILD_JOBS}" -gt 0 ]]; then
  CPUS="$BUILD_JOBS"
else
  CPUS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
fi
echo "[build] parallel jobs: ${CPUS} (all cores)"
# Default cmake output is the "[ N% ] Building ..." lines. Printing every
# nvcc command as well made the CUDA jobs too slow to finish inside the
# CI timeout (prism was at 32% and stock at 41% when stopped).
"${LINEBUF[@]}" cmake --build "$BUILD_DIR" --config Release -j"$CPUS" --target llama-server

BINARY="$BUILD_DIR/bin/llama-server"
if [[ ! -x "$BINARY" ]]; then
  echo "[FAIL] build did not produce $BINARY"
  exit 1
fi

# --- verify: binary exists and --help works -------------------------------
if ! "$BINARY" --help >/dev/null 2>&1; then
  echo "[FAIL] $BINARY --help failed (exit $?)"
  exit 1
fi
VER="$( "$BINARY" --version 2>&1 | grep -m1 version | head -1 || true )"
echo "[OK] built $BINARY ($VER); --help exit 0"

# --- cuda link check (proves the cuda variant genuinely linked cuda libs) ---
if [[ "$BACKEND" == "cuda" ]]; then
  echo "[build] verifying CUDA linkage"
  if command -v ldd >/dev/null 2>&1; then
    ldd "$BINARY" | grep -E 'libcuda\.so|libcudart\.so|libcublas\.so' \
      || { echo "[FAIL] cuda binary does not link cuda runtime libs"; exit 1; }
    echo "[OK] cuda binary links cuda runtime libs"
  else
    echo "[build] ldd not available; skipping cuda link check"
  fi
fi

# Emit the resolved binary path (last line, consumed by CI / make).
echo "$BINARY"

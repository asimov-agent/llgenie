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

# Resolve url/branch per tree.
if [[ "$TREE" == "prism" ]]; then
  REPO_URL="https://github.com/PrismML-Eng/llama.cpp.git"
  BRANCH="prism"
  TREE_DIR="$SERVER_ROOT/prism-llama.cpp"
  echo "[build] tree=prism (PrismML-Eng/llama.cpp, branch=$BRANCH) at $TREE_DIR"
else
  REPO_URL="https://github.com/ggerganov/llama.cpp.git"
  BRANCH="master"
  TREE_DIR="$SERVER_ROOT/llama.cpp"
  echo "[build] tree=upstream (ggml-org/ggerganov llama.cpp, branch=$BRANCH) at $TREE_DIR"
fi

if [[ "$BACKEND" == "metal" ]]; then
  BUILD_DIR="$TREE_DIR/build-metal"
  CMAKE_FLAGS="-DGGML_METAL=ON -DGGML_CUDA=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF"
elif [[ "$BACKEND" == "cuda" ]]; then
  BUILD_DIR="$TREE_DIR/build-cuda"
  CMAKE_FLAGS="-DGGML_CUDA=ON -DGGML_METAL=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF"
else
  BUILD_DIR="$TREE_DIR/build-cpu"
  CMAKE_FLAGS="-DGGML_METAL=OFF -DGGML_CUDA=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF"
fi

echo "[build] backend=$BACKEND build-dir=$BUILD_DIR"

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
  command -v "$NVCC" >/dev/null 2>&1 || { echo "[FAIL] nvcc not found; cuda build needs the CUDA toolkit (see CI 'install cuda toolkit' step)."; exit 1; }
  echo "[build] nvcc: $NVCC ($(nvcc --version | head -1 2>/dev/null || true))"
fi
if [[ "$BACKEND" == "metal" && "$(uname -s)" != "Darwin" ]]; then
  echo "[FAIL] metal requires macOS (uname -s != Darwin). Cannot build a Metal backend here." >&2
  exit 1
fi

# --- clone-or-pull to the latest commit -----------------------------------
if [[ -d "$TREE_DIR/.git" ]]; then
  echo "[build] $TREE_DIR already exists -> fetching latest of branch $BRANCH"
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
echo "[build] configuring: cmake -S $TREE_DIR -B $BUILD_DIR -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS"
cmake -S "$TREE_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS
echo "[build] building llama-server (this is the slow part)"
# Portable core count: nproc (Linux) or sysctl hw.ncpu (macOS). macOS has no
# nproc by default; this keeps the bare-metal Mac build portable.
CPUS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
cmake --build "$BUILD_DIR" --config Release -j"$CPUS" --target llama-server

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

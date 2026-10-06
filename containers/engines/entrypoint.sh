#!/usr/bin/env bash
# Entrypoint for every llgenie engine image (containers/engines/Dockerfile).
# Engine, backend and GPU arch are baked in (LLGENIE_ENGINE/BACKEND/VARIANT);
# install, env and the launch line come from the frozen params.json that the
# image was built from (generated from the engine's skill by make engine-params).
#
#   serve    (default) serve $LLGENIE_MODEL as llm-local on $LLGENIE_HOST:$LLGENIE_PORT
#   health   exit 0 when the OpenAI API answers (used by HEALTHCHECK)
#   detect   print the installed engine version
#   version  alias of detect (the engine binary's --version; safe on GPU-less hosts)
#   info     image metadata (engine, backend, GPU arch, port, base_url)
#   shell    interactive bash
#   <cmd>    run anything else
#
# Env: LLGENIE_MODEL (required for serve; a path under /models or an HF repo id),
#      LLGENIE_PORT (11434), LLGENIE_HOST (0.0.0.0), LLGENIE_DRAFTER, HF_TOKEN.
set -euo pipefail
cd /opt/llgenie/app
ENGINE="${LLGENIE_ENGINE:?image has no LLGENIE_ENGINE}"
BACKEND="${LLGENIE_BACKEND:?image has no LLGENIE_BACKEND}"
PORT="${LLGENIE_PORT:-11434}"
HOST="${LLGENIE_HOST:-0.0.0.0}"

cmd="${1:-serve}"
[[ $# -gt 0 ]] && shift
case "$cmd" in
  serve)
    MODEL="${LLGENIE_MODEL:-${1:-}}"
    [[ -n "$MODEL" ]] || { echo "[entrypoint] set LLGENIE_MODEL (path under /models or HF repo id)" >&2; exit 2; }
    echo "[entrypoint] ${ENGINE}/${BACKEND} -> OpenAI API on ${HOST}:${PORT}/v1 (model llm-local)"
    exec python3 engine_runner.py serve params.json \
      --model "$MODEL" --host "$HOST" --port "$PORT" --drafter "${LLGENIE_DRAFTER:-}"
    ;;
  health)
    curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null
    ;;
  detect)
    exec python3 engine_runner.py detect params.json
    ;;
  version)
    # engine binary version (works on GPU-less runners; the engine is not started)
    exec python3 engine_runner.py detect params.json
    ;;
  info)
    printf 'engine=%s backend=%s variant=%s cuda_arch=%s gpu_targets=%s port=%s base_url=http://<host>:%s/v1 model=llm-local\n' \
      "$ENGINE" "$BACKEND" "${LLGENIE_VARIANT:-}" "${LLGENIE_CUDA_ARCH:-}" "${LLGENIE_GPU_TARGETS:-}" "$PORT" "$PORT"
    ;;
  shell)
    exec bash "$@"
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac

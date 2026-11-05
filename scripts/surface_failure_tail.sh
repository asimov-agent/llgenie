#!/usr/bin/env bash
#
# surface_failure_tail.sh — surface the real exit-2 stderr of a command in the
# GitHub check-run annotation (issue #1714).
#
# A main-only live step (ci-hf-live's check-model-links / check-registry /
# check-quant-catalog / test-unit-network, and pipeline's ci-top-tier) fails with
# `make ... Error 2` whose REAL cause lives in the target's own log tail (e.g.
# `... is gone`, an AssertionError, a `make: *** [...] Error 1`), but the Actions
# check-run annotation shows only the generic runner wrapper — the Node.js 20
# deprecation warning and `##[error]Process completed with exit code 2.` — with
# no trace. That makes flake-vs-drift undecidable from the check, forcing a
# manual log pull.
#
# This helper runs the command with its combined output teed to LOGFILE, and on
# a non-zero exit emits the ANSI-stripped tail of LOGFILE as `::error::` workflow
# commands. GitHub renders those as check-run annotations on the commit, so the
# annotation on a failing live step carries the real cause instead of the wrapper.
#
# Usage:
#   surface_failure_tail.sh <logfile> -- <command> [args...]
#
# Exit code: the wrapped command's exit code (0 on success, non-zero on failure),
# so the step still fails exactly when the target fails — the gate is never
# weakened, only the annotation is enriched.
set -u

logfile="$1"; shift
[ "$1" = "--" ] && shift

set +e
"$@" 2>&1 | tee "$logfile"
rc=${PIPESTATUS[0]}
set -e

if [ "$rc" -ne 0 ]; then
  # Emit the tail of the target's real output so flake-vs-drift is decidable from
  # the check-run annotation. Strip ANSI/escape sequences and empty lines, keep
  # the last 40 non-empty lines.
  echo "::error title=Live step failed (exit $rc)::"
  sed 's/\x1b\[[0-9;]*m//g' "$logfile" \
    | grep -vE '^[[:space:]]*$' \
    | tail -n 40 \
    | while IFS= read -r line; do
        echo "::error::$line"
      done
fi

exit "$rc"

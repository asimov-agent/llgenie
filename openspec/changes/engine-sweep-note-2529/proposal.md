# Proposal: engine-sweep-note-2529

## Why

Issue #2529 (under umbrella #2504, landed via PR #2517) demands the sweep PROOF for the
engine × arch non-root cutover: a committed record that every shipped engine cell was
rebuilt and re-published at a fresh post-#2517 context hash, runs its image as a non-root
user, and that the last failing cell of the cutover wave (vllm/rocm, exit 126 defect on
`3a4d82f5-db98981b-rocm`) was remediated and re-verified green. The measurements exist
(gate rc=0, imagetool reads, CI dispatch verdicts) but live only in chat history — the
issue's acceptance criteria require the sweep table + note to be IN the repo.

Issue: #2529. Umbrella: #2504. Non-root engine PR: #2517.

## What Changes

- `agent-wiki/2026-11-13-engine-build-sweep-2529.md`: the sweep proof note — pin/referee state (28 committed cells published at fresh hashes), populations named (30 variants, 4 disabled by design), per-tag non-root reads (`1000:1000` for all 28), trivy DS-0002 = 0 with reconcile evidence, and the vllm-rocm remediation + verify-dispatch verdict (run 43361645161, completed success), plus the 28-row table.
- `docs/changes.d/2026-11-13-engine-build-sweep-2529.md` index row; `CHANGES.md` regenerated.
- No code change.

## Impact

- Docs only; #2529's remaining acceptance evidence becomes repository state and the issue can close COMPLETED with all criteria proven.

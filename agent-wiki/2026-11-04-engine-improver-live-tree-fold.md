# Fold 34 live-only engine-improver skill references + scripts into the tree (#1724, live-parity)

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` failed: the host profile had
accumulated **34 files live-only** (29 references + 5 scripts under
`skills/llgenie-engine-improver/`) with no tree counterpart, plus 2 live-longer references and 2
additive reference updates. Every live-only file is a finding in `check_agent_profiles.py` — an
*unversioned, unreviewable* instruction (#1060/#791). The contract is one-way tree→live and says fix
the TREE: commit the live content into `agents/<profile>/` via issue+PR, then re-sync (#1724).

## The fold (live authoritative, tree follows)

38 files copied verbatim from the live profile
(`~/.hermes/profiles/llgenie-engine-improver/skills/llgenie-engine-improver/…`) into
`agents/llgenie-engine-improver/`:

- 29 `references/*.md` added (engine-build-proof-dispatch, ci-run-watching, engine-image-cells,
  pr-vehicle-checks, proving-and-pitfalls, rocm-build-verification, …) + 2 live-rich files folded
  larger live→tree:
  - `references/ci-run-watching.md` 38,720 → 47,820 b
  - `references/engine-image-cells.md` 9,923 → 11,449 b
- 5 `scripts/*` added: `engine_image_tags.sh`, `ghcr_publish_probe.sh`, `measure_live_admission.py`,
  `probe_rocm_resolution.sh`, `prove_measurements_consult.py`

Additive only — no content rewritten (2 live-longer folded live→tree; the 2 tree-ahead rows left as
the corrected pre-sync state a later sync then delivers).

## Verified after the fold

`check-agent-profiles` absent-from-tree for this lane = **0** (was 34); `check-agent-skills` OK;
`check-docs` ok; `changes-index` ok; `check-pr-hygiene` OK; `make lint` LINT OK (one folded file was
missing a trailing newline — appended). The engine-improver lane now matches the doc-maintainer fold
from this change-note, closing the #1724 propagation gap for a second lane.

# 2026-11-25 — the trend matrix re-rendered from the live trending (issue #3056)

OpenSpec change: `trend-list-matrix-rerender-3056`. Issue: [#3056](https://github.com/asimov-agent/llgenie/issues/3056). PR: opened from `feat/trend-list-matrix-rerender` (see #3056).

## What was verified against the spec

The `trend-list-matrix` spec requires the committed matrix (`tests/fixtures/trend-list-matrix.json`)
and its recorded Hub answers (`tests/fixtures/hub-snapshot.json`) to answer the SAME live trending
read. The staleness read shipped in the #2901 lane (`make check-trend-list-fresh`) measured the drift
on `main` and filed it as issue #3056: 4 cells disagreed, all `metal/24/*`, each
`smallest GGUF is 6 GB > 10 GB this host can hold` in the fixture against `… is 10 GB …` live
(fingerprint `866ec6ad00f3`).

The re-render ran the post-merge step-5 order exactly (`docs/post-merge-live-verify.md`):
`make -s sync-registry` → `make -s sync-quant-catalog` → `make -s render-trend-list-matrix` →
`make -s render-engine-skill-gap` → `make -s skills-validate`, then the two trend gates. Measured at
this lane's head:

- `sync-registry` rc=0, `sync-quant-catalog` rc=0 — the quant snapshot re-vendored
  (`tests/fixtures/quant-catalog-hub-snapshot.json`), `data/trending-README.md` re-written.
- `render-trend-list-matrix` rc=0 → 81 cases + 103 Hub answers; the matrix delta is exactly the 4
  named cells (4 lines), no other cell moved.
- `check-trend-list-matrix` rc=0 (hermetic replay of the new pair), `render-engine-skill-gap` rc=0,
  `skills-validate` rc=0 (18 skills, registry 18 engines, 0 errors).
- `check-trend-list-fresh` rc=0: `the fixture agrees with the live trending in all 81 cells
  (fingerprint 8b5bb053568fd9f1, registry 2026-11-17T08:25:02Z)` — the drift fingerprint is gone.
- `make openspec-validate NAME=trend-list-matrix-rerender-3056` rc=0.

## Decisions

- Data-only change: no gate, picker or monitor behaviour moved. The proposal's `Impact` list was
  corrected to name what the fixed order ACTUALLY rewrites (`data/trending-README.md`,
  `tests/fixtures/quant-catalog-hub-snapshot.json`, `data/engine-skill-gap.json`) instead of the
  `docs/trending-*.md` pair it had guessed at.
- The re-render carries the sync outputs with it rather than leaving them as an untracked residue on
  the branch: the fixture+snapshot pair and the re-vendored quant snapshot land on one commit, so the
  hermetic replay and the live read agree on the same SHA.
- `Not covered` is one linked issue, not prose: the filing path itself (`ci-hf-live` step 10 dying with
  exit 2 when a named drift has no refresh issue) is issue [#3057](https://github.com/asimov-agent/llgenie/issues/3057).

## Current status

Branch `feat/trend-list-matrix-rerender`, opened as PR #3064 against `main`; `closes #3056`. The
battery proof and the green `check-trend-list-fresh` read on `main` after the merge are the closing
evidence (`make post-merge-live-check`).

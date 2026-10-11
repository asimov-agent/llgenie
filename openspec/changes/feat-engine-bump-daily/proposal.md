# feat-engine-bump-daily — proposal

## Why

Every engine skill in `skills/engines/*/SKILL.md` pins an upstream commit
(`pinned`) plus the build parameters that match it (`cmake_flags`, `hw_flags`,
`toolchain`, `launch`, image digests). Today that pin is moved **by hand**, so
pins go stale, and when someone does move one, nothing checks the build
parameters against the new upstream tree — upstream renames slip through until
an image breaks (`LLAMA_CUBLAS` → `GGML_CUDA`, `AMDGPU_TARGETS` →
`GPU_TARGETS`, a new required `-DGGML_BACKEND_DL`, a CUDA/ROCm toolkit bump, a
renamed server flag).

This change makes the weekly pin mechanical and **safe**:

- A cron workflow polls each engine's upstream repo, finds the latest commit for
  its `ref` (branch head or highest stable tag), and bumps `pinned`/`ref`/
  `version`/`verified` when it moved.
- It **derives the build parameters from the upstream tree at that commit with
  plain code** (git, regex, file parsing — no LLM anywhere), so the architecture
  we build for keeps the correct flags. The same input always gives the same
  output.
- **The core safety gate:** if the upstream diff between the old and new pin
  touches any build-sensitive file (`upstream_watch`), the bump does **not**
  silently guess. Renames and known moves are auto-applied; a removed option or
  launch flag is recorded as a **hard-fail** — the pin still moves and a PR is
  still created, with the hard-fail flagged in the PR body so a human fixes the
  skill (CI goes red on the build). `main`'s pin is never touched directly.
- The bump opens a PR per changed engine; that PR's CI builds and tests **only**
  the changed engine × arch images. A PR exists ⟺ the plan found ≥1 new hash.

Supersedes #100 (its "update the skill with an agent" step is replaced by the
deterministic param derivation below).

## What Changes

- `scripts/engine_bump.py` — `plan` (git ls-remote → which engines moved),
  `pin` (targeted frontmatter edit), `bump` (pin + derive + apply + regen),
  `bump-daily` (what the workflow runs). Stdlib only.
- `scripts/engine_params_derive.py` — deterministic extractors (E1–E9) that read
  the upstream tree at a sha via `git show <sha>:<path>` on a
  `--filter=blob:none` clone and produce a stable `findings` JSON.
- A `derive:` frontmatter key per skill declaring which extractors apply, so the
  generic code has no per-engine `if`.
- `engine-bump.yml` — `plan` job + `bump` matrix job, weekly cron `23 6 * * 1` (Monday) +
  `workflow_dispatch`, gated to collaborators/owner/bot only. Runs on its **own**
  cron, separate from the registry sync (`registry-sync.yml`, daily cron `17 5 * * *`),
  so the two jobs run at different times and never block each other.
- `ci.yml` `changed-engines` step on `pull_request` — build/test only the
  engines whose params differ from the base branch.
- Make targets: `engine-bump-plan`, `engine-derive`, `engine-bump`,
  `engine-bump-daily`.
- README section "Weekly sync: registry + engine pins".

## Out of scope

- Merging the bump PRs (a reviewer merges, per AGENTS.md).
- Building engines on the host (all engine work stays in images).
- The registry sync itself (existing #105 logic, kept unchanged).

## Acceptance (summary)

- `make engine-bump-plan` against real upstreams returns the correct new
  head/tag and never moves backwards.
- A pin edit changes only `pinned`/`ref`/`version`/`verified`/digest.
- E2 rename auto-applies; E3 removed option and E8 removed launch flag hard-fail
  with a deduped issue; E4/E5/E6/E7 auto-apply; E9 reports per-backend.
- `make engine-derive` is byte-deterministic for a fixed sha.
- A PR changing only one engine's params runs engine-image jobs for that engine
  only; a push to `main` still runs the full matrix.
- `make engine-bump-daily DRY=1` runs end-to-end without pushing.
- OpenSpec change validates; loop gate green.

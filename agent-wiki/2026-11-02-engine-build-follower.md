# Engine build changes open a follower at PR time (issue #1085)

An engine build change — a change to HOW cells are built (source-build, pin, Dockerfile, toolchain,
`entrypoint.sh`, `engine_runner.py`) — cannot be proven by the author reporting `available -> no
rebuild`, which is a cache hit on an image CI already published and carries no build timing. So every
such change opens a **follower issue, delegated to `llgenie-engine-improver`, AT PR time** (not after
merge), scoped to execution rather than review:

1. dispatch `engine-build` COLD at the PR head — `gh workflow run 395994204 --ref <branch> --field
   engine=<id> --field arch= --field force=true --field push=true` — and quote the run id;
2. serve at least one cell to READY from the just-published image and record the stage `detect` output;
3. record per-cell build wall-clock (job step timings) and image size (published manifest) beside the
   run id in the change note;
4. post the re-measured acceptance criteria on the implementing PR/issue with quoted commands.

Reconciles the lane's "CI is the sole builder" rule explicitly: the pipeline result carries the
timing (a wall-clock / image size comes from CI, never a local build), so a verification build is not
required. Also executes the first instance — #1085 → #1075 (ollama ×4): cold build of all four cells
(run 41420879842 @ head `4e533896`, wall-clock cpu 569s / vulkan 1228s / cuda 5161s / rocm 5253s;
image size 73.4 / 164.4 / 2245.6 / 6221.1 MiB; all four `test-engine-stage` + push + publish success;
only the cuda install-leg red, the known #1027 container-install seam).

Issue #1085. The versioned pattern lives in `agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md`.

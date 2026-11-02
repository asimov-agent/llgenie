# 2026-11-02 vllm bump-fix: preinstall torch==2.14.0 to match the sha's cpu.txt/cuda.txt (issue #1544)

The #1520 pin move (vllm `v0.33.0@3a4d82f5`) left the skill's preinstall torch pinned at `2.13.0`
(the previous sha's pin), so the cpu cell that previously built fell apart: `engine-build` publish
run `41382485751` failed at `make build-engine ENGINE=vllm ARCH=cpu` with uv
`no version of torch==2.14.0+cpu ... your requirements are unsatisfiable`.

## What was actually wrong (measured from the run log + the pinned file)

- `requirements/build/cpu.txt` at `3a4d82f5` pins `torch==2.14.0+cpu` (it was `==2.13.0+cpu` at the
  previous pin `5df63a72`).
- The skill's cpu step 1 preinstall (`torch==2.13.0 torchvision torchaudio torchcodec --index-url
  .../whl/cpu`) installed `2.13.0+cpu`.
- The skill's cpu step 2 `uv pip install -r .../requirements/build/cpu.txt --index-strategy
  unsafe-best-match` then demands `torch==2.14.0+cpu`, but that command does not carry the cpu
  index, so it resolves against the default mirror (PyPI), where no `+cpu` wheel exists → the exact
  `unsatisfiable` in the run log.

So it was NOT a missing wheel (torch `2.14.0+cpu` exists on the cpu repack index) — it was a stale
preinstall pin ("the pin moved" class, not "another input moved"). The step-2 `-r` resolution can
only be satisfiable after step 1 has installed the sha's own torch pin from the same repack index;
the recipe's step-1 pin must track `cpu.txt` (and `cuda.txt`) whenever an upstream bump changes them.

The same class applies to the cuda cell: `cuda.txt` also moved `torch==2.13.0` → `torch==2.14.0` at
this sha, and the cuda preinstall was still `2.13.0`. rocm is untouched (`rocm.txt` still
`torch==2.12.0+rocm7.14.0`; the rocm recipe has no separate torch preinstall).

## Fix

Edit `skills/engines/vllm/SKILL.md` (params are generated — never hand-edit `params/vllm.json`):
bump both the cuda and cpu preinstall rows from `torch==2.13.0` to `torch==2.14.0` and add an "NB:
this preinstall pin MUST track the sha's own cpu.txt torch pin" comment so the next bump updates it.
Regenerate with `make generate-engine-params`.

## Proof

Reproduced the exact failure in the `base-cpu` container at the committed pin:
- old recipe (preinstall `torch==2.13.0`, then `-r cpu.txt`): `× No solution found ... torch
  ==2.14.0+cpu ... your requirements are unsatisfiable` — byte-for-byte the run-`41382485751` log.
- fixed recipe (preinstall `torch==2.14.0`, then `-r cpu.txt`): resolves and installs cleanly,
  `+ torch==2.14.0+cpu` and the build deps.

`make build-engine ENGINE=vllm ARCH=cpu` at head `854228d2` (and the doc commit on top): BUILD SUCCESS
(local run, base-cpu container). The `engine-build` publish dispatch `<run>` then re-verifies + pushes all three vllm cells.

## Acceptance status (measured)

- Fix resolution proven in the base-cpu container at the committed params (exact run-`41382485751`
  failure reproduced and shown green with the fixed preinstall; see Proof above).
- PR adds the change-note trio (agent-wiki + docs/changes.d + CHANGES.md row) and closes #1544;
  vllm stays pinned at `3a4d82f5` (no engine-bump; the fix belongs in the skill).
- Full `make build-engine ENGINE=vllm ARCH=cpu` and the published `-cpu` image are verified by the
  `engine-build` workflow dispatch (this lane never builds/pushes locally) and recorded at the run id
  when the PR's publish proof completes.

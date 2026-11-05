# Verifying an engine flag-contract finding

A "flag-contract" finding says an engine's skill/manifest claims its binary answers flags the binary
does not answer. Decide it from the source, at a fresh sha, and separate the two layers below — they
have different fixes and only one of them unblocks a publish.

## Verify at a fresh origin/main, read via `git show`

Re-derive the contract lines from the canonical remote, never from memory, chat, or a PR worktree:

    git -C <repo> fetch origin main            # canonical remote is asimov-agent/llgenie (named `origin` or `fork`; `upstream` may not exist)
    MAIN=$(git -C <repo> rev-parse origin/main)
    git -C <repo> show $MAIN:skills/engines/<id>/SKILL.md
    git -C <repo> show $MAIN:containers/engines/binaries.json

- `skills/engines/<id>/SKILL.md` declares `binary_flags: [...]` and the `detect`/launch lines.
- `containers/engines/binaries.json` → `/engines/<id>/<backend>` carries `{binary, flags, probe}`; this
  is what the publish gate actually reads (`binary_manifest`/`variant_flags` in `scripts/engine_image.py`).
- For the installed-binary behaviour, read the upstream CLI source you measured (e.g. the cuda zig
  `cuda_main.zig`): its own `--help`/`--version` branch lines are the expected-vs-got evidence.

## The publish gate is DOUBLE-LOCKED — a text fix never unblocks publish

`scripts/engine_image.py` judges flags in two independent layers:

1. **Documented-flags rule** — every flag in `binaries.json` for the cell must answer on its own.
2. **Family rule, UNCONDITIONAL** — `TYPED_FLAGS = ("--version", "-h", "--help", "-V")` is always
   probed regardless of what the manifest documents, and the help family (`-h`/`--help`) and version
   family are each required. **No `probe` policy waives the help family** — even `probe: help` (the
   argparse-only case) still requires it.

So narrowing `binary_flags`/`flags` to the honest set is correct but **does not make the cell
publishable**. State that plainly in the finding: the binary is the blocker, the gate is working as
designed. A gate that admits a "--version and nothing else" binary is exactly the failure `#580` fixed.

## Separate the two defects and name the right owner

- **Skill/doc layer (this lane frames):** the manifest `flags` / SKILL `binary_flags` lists a spelling
  the binary lacks. Fix = text, per-backend aware — a cuda zig CLI answers `--version` only while a
  prebuilt macos binary answers both, so use the per-backend `BINARY_FLAGS`/`BINARY_PROBES` path in
  `scripts/engine_skills.py` rather than one blanket list.
- **Binary layer (upstream, do NOT patch here):** the engine CLI has no help spelling. Publishing stays
  blocked at that pin until upstream adds one — never patch upstream (`#687`).

## Evidence shape to post on the carrier issue

Open with the lane/issue/branch/measured-sha line, then: the exact contract lines (file + line), the
measured expected-vs-got (each flag's exit code), the gate's unconditional family verdict with its
line numbers, the verdict (defect vs WAI), and proposed acceptance for the planner to refine. Keep it
source-grounded — the planner refines and dispatches; this lane frames, an implementer implements.

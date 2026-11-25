# 2026-11-25 — engine-bump re-stamp leg: the 2026-11-23 wave's 7 open bump PRs, read and classified (issue #3054)

## What was verified against the issue

- The issue's measured symptom was re-measured live before any code: `make -s engine-bump-restamp`
  (dry) rc=0 read all 7 open `chore/engine-bump-*` pull requests (#3029 ollama, #3030 vllm,
  #3031 tensorrt-llm, #3032 llama.cpp-prism, #3033 llama.cpp, #3034 tensorfold, #3035 edge0) and
  named the composition defect on each — `glued OPENSPEC line` on six, `no own acceptance criteria
  section` on #3031 — plus the red lanes each body defect reddens (`guard`, `scope`, `ci-verdict`,
  `linux / unit`, `trigger`).
- **Classification, not guesswork:** every bump was compared against the pin `main` actually carries
  (`skills/engines/<engine>/SKILL.md` `pinned:`, read from `origin/main` through `gh api`). All 7 came
  back `pending` — `tally pending=7 landed=0 superseded=0 unknown-pin=0` — i.e. no bump of this wave
  was overtaken, so the honest remediation is re-stamp-every-body and **close nothing**; the
  `closed as overtaken` path exists for a wave that really moved on.
- `scripts/engine_bump_restamp.py` re-renders each body through the ONE existing composer
  (`scripts/engine_bump_pr_body.render_body`, issue #3050) and writes only through the guarded seam
  (`scripts/bot_preflight.py --stamp` -> `scripts/pr_body_write.py --pr … --new …`, i.e.
  `make bot-stamp-body` then `make bot-body-write`, issue #2131). It never issues `gh pr edit`, never
  merges, and re-reads the live body after every write to prove the `OPENSPEC:` line now resolves.
- Defects the leg names (found while testing, in the leg, not in the tests): `GLUED_OPENSPEC_LINE`
  back-tracked into a clean `OPENSPEC: <change>` line and had to anchor on the literal `#`; the review
  cut swallowed `## Acceptance criteria` and now stops at the next `^#{2,3} ` heading; kind tallies
  were computed and thrown away; `written` counted a write the seam had refused or left unchanged, so
  `refused` / `unstamped` / `unchanged` are now separate counters.
- Dry-by-default verified: the rc=0 live read wrote nothing (`written=0 closed=0`) and put every
  rendered body under `OUT_DIR`.

## Key decisions

- No CI clock names this target: rewriting an OPEN pull request body is the host's act, and the #3050
  composer already fixes every FUTURE wave at render time. The leg therefore carries a test (so CI
  reaches it) but no `host-only-wiring.json` entry and no workflow reference — the wiring gate's own
  staleness rule demanded the entry's deletion.
- `docs/BOTS.md` prose + `make bots-targets-index` instead of a `docs-exceptions.json` excuse.
- The residual `linux / unit` red on these bump PRs is the pins-published race, already its own lane:
  issue #3051 / PR #3062 (`make engine-pins-await` + `PINS-PENDING` deferral). This lane fixes the
  body half (`guard`, `scope`) and does not pretend to fix the unit half.

## Applied remediation (same day, head `7e6b070a0`)

- The stamp guard was changed to compare a proven tick by its CLAIM (the composer's
  `ACCEPTANCE_CLAIMS` sentence), not its whole line: a re-cited `(proven: …)` clause at the head is a
  carry, a re-worded claim is still refused. Measured on PR #3030's live body: the claim-carry reaches
  the write where the old line-equality seam skipped the item.
- `make -s engine-bump-restamp APPLY=1 DEFERRED="ollama=3065 llama.cpp=3066"` ran through the guarded
  seam: `tally pending=7 landed=0 superseded=0 written=5 refused=2 closed=0 unproven=0`. Five bodies
  (#3030, #3031, #3032, #3034, #3035) were rewritten and re-read green
  (`OPENSPEC=resolvable`, three `(proven: …)` ticks each). The seam REFUSED #3029 and #3033 because
  their live bodies carry the images tick the composer cannot prove at those heads (ollama's four
  variants build red — issue #3065; llama.cpp's vulkan build never ran — issue #3066); the refusals are
  the guard doing its job (issue #2131), not a leg failure.
- The wave's landing half is now its own tracking issue #3071 (each bump merged or closed with the
  superseding pin named), gated on the await seam (#3051 / PR #3062) and the two image-gap issues.

## Current status

Leg, 44 hermetic tests (26 leg + 18 seam/guard), target, docs and OpenSpec change are in the branch at
`7e6b070a0`; `lane-preflight` OK (7 gates), `check-docs` ok (382 targets), `openspec-validate` passes,
and the applied re-stamp tally above is the live read. The wave's per-PR landings follow through #3071.

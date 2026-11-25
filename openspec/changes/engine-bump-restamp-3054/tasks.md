# Tasks: re-stamp the 2026-11-23 bump PRs through the body seam (issue #3054)

## 1. Read the live wave through one make target

- [x] `scripts/engine_bump_restamp.py` + `make engine-bump-restamp` enumerate every OPEN
      `chore/engine-bump-*` pull request and read each live body's bump facts (`**Engine:**`,
      `**Pin:** old -> new (ref)`, the full compare shas). Proven: `make -s engine-bump-restamp`
      rc=0 — 7 bumps read (#3029 ollama, #3030 vllm, #3031 tensorrt-llm, #3032 llama.cpp-prism,
      #3033 llama.cpp, #3034 tensorfold, #3035 edge0), each naming its red lanes and its body
      defect (`glued OPENSPEC line` on six, `no own acceptance criteria section` on #3031).

## 2. Classify against the pin `main` ACTUALLY carries

- [x] `main_pin` reads `skills/engines/<engine>/SKILL.md` frontmatter `pinned:` from `origin/main`
      through `gh api`, and `classify_against` returns `pending` / `landed` / `superseded` /
      `unknown-pin` before any write. Proven: the same rc=0 run tallies
      `pending=7 landed=0 superseded=0 unknown-pin=0` (every bump's `main-pin` equals its `old`).

## 3. Re-render through the ONE composer, never a second one

- [x] `render_for` calls `scripts/engine_bump_pr_body.render_body` with the facts read from the live
      body, and `read_facts`/`GLUED_OPENSPEC_LINE`/`NEXT_SECTION` name the composition defects the
      leg is repairing (glued `OPENSPEC:` heading, swallowed `## Documentation review`, missing
      acceptance section, compare shas disagreeing with the pin line). Proven:
      `pytest tests/test_engine_bump_restamp.py -q` rc=0 (composer round-trip + every defect case).

## 4. Write only through the guarded seam, and only after the stamp authority

- [x] apply mode calls `scripts/bot_preflight.py --stamp` (`make bot-stamp-body`) then
      `scripts/pr_body_write.py --pr <n> --new <rendered>` (`make bot-body-write`, issue #2131),
      re-reads the body after the write, and issues no raw `gh pr edit`; a refused stamp/write
      tallies `unstamped` / `refused` / `unchanged` instead of claiming a write. Proven:
      `test_apply_writes_only_through_the_guarded_seam_after_the_stamp` and
      `TestProcessRefusals` pass (`pytest … -q` rc=0).

## 5. Close an overtaken bump with main's pin as the evidence — never merge

- [x] `CLOSE_SUPERSEDED=1` closes a `landed`/`superseded` bump with `close_comment` naming main's
      live pin, prints `closed as overtaken`, and no code path calls `gh pr merge`. Proven:
      `test_landed_and_superseded_close_with_the_pin_evidence` (asserts zero seam/merge calls)
      passes, rc=0.

## 6. Dry by default

- [x] Without `APPLY=1` the leg writes nothing: one line per bump plus a tally, drafts under
      `OUT_DIR`. Proven: the rc=0 live read reported `written=0 closed=0` and wrote no body.

## 7. Tests are hermetic and repo-gate-clean

- [x] `tests/test_engine_bump_restamp.py` (26 tests, `FakeProc` in place of `scripts/proc.py`, no
      network, no real PR write). Proven:
      `pytest tests/test_engine_bump_restamp.py tests/test_package_layers.py -q` rc=0 — 42 passed.
- [x] Layering declared: `engine_bump_restamp` in the Product group with its two real cross-group
      edges (`-> proc`, `-> check_pr_hygiene`). Proven: `make -s check-package-layers` rc=0 —
      "191 modules in 5 groups, 81 cross-group edges all stated, 0 cycles".
- [x] Wiring: the leg is wired through its target and carries NO host-only `documents` entry (its
      test makes it CI-reachable) while no CI workflow names it, so no clock rewrites an open body.
      Proven: `make -s check-wiring` rc=0 — "496 documents (10 host-only), 420 targets, 158 host-only".
- [x] Docs: `make engine-bump-restamp` documented in `docs/BOTS.md` and the generated target table
      re-rendered. Proven: `make bots-targets-index` then `make -s check-docs` rc=0 —
      "every one of the 382 user-facing make targets is documented".
- [x] Subprocess/import discipline. Proven: `make -s lint` rc=0, `make -s check-proc-gate` rc=0,
      `make -s check-import-roots` rc=0, `make -s check-workflows` rc=0.

## 8. Pre-push proof

- [x] `make lane-preflight` prints `preflight: OK` for the fast gates at the branch head it pushes.

# ci: re-stamp the 2026-11-23 bump PRs through the body seam, or close them as superseded

Issue: [#3054](https://github.com/asimov-agent/llgenie/issues/3054)

## Why

The 2026-11-23 engine-bump wave opened 7 pull requests — #3029 (ollama), #3030 (vllm), #3031
(tensorrt-llm), #3032 (llama.cpp-prism), #3033 (llama.cpp), #3034 (tensorfold), #3035 (edge0) — and all 7
are still open at `mergeStateStatus=BLOCKED`. Their bodies are the ones `make engine-bump-pr-body`
(issue #3050, landed in PR #3058) was written to prevent. Measured on the live body of PR #3030:

```
- **Pin:** `3a4d82f5` -> `0c57b419` (`v0.34.0`)
...
OPENSPEC: publish-changed-pin-images## Documentation review
```

`OPENSPEC_REF` in `scripts/check_pr_hygiene.py` is `^OPENSPEC:\s+([A-Za-z0-9_-]+)\s*$`: a change name with a
heading glued after it matches nothing, so `guard` (`make check-pr-openspec-change`, mk/gates.mk:139) reports a
missing change, and the bodies carry no `## Acceptance criteria`, so `scope` (`make
check-pr-acceptance-form`, mk/gates.mk:142) reddens on the same 7. The composer fix only reaches the NEXT
wave: nothing re-renders the bodies that are already open, so 7 real pin bumps sit unmergeable and the board
carries 7 red pull requests whose redness is a composition artifact.

## What Changes

- **New host-side leg:** `scripts/engine_bump_restamp.py` + `make engine-bump-restamp` read every OPEN
  pull request whose head branch is `chore/engine-bump-<engine>`, extract its bump facts from the live body
  (`**Engine:**`, `**Pin:** old -> new (ref)`, the full compare shas), re-render the body through the ONE
  existing composer `scripts/engine_bump_pr_body.render_body` (no second composer, no inline bash), stamp it
  through `make bot-stamp-body`'s authority (`scripts/bot_preflight.py --stamp`) and write it back only through
  the guarded seam `scripts/pr_body_write.py` (`make bot-body-write`, issue #2131). A raw `gh pr edit --body-file`
  is never issued by this leg.
- **Classification before writing:** each bump is compared against the engine pin `main` ACTUALLY carries
  (`skills/engines/<engine>/SKILL.md` frontmatter `pinned:`, read from `origin/main` through `gh api`):
  `pending` (main still holds the PR's old pin) is re-stamped; `superseded` (main moved past the old pin, or
  already holds the new one) is closed with a comment naming main's live pin as the evidence — never merged,
  never re-stamped as if it were pending work.
- **Dry by default:** the target prints one line per bump plus a tally and writes nothing; `APPLY=1` enables
  the guarded writes, `CLOSE_SUPERSEDED=1` additionally closes superseded bumps with the evidence comment.
  Every write is re-read from `gh pr view --json body` afterwards.
- **The body gates are re-evaluated by a GitHub event:** a body write through the seam is the event that
  re-runs `check-pr-openspec-change` / `check-pr-acceptance-form` on the push lane the PR carries; no CI
  pipeline is dispatched by this leg (issue #2701 discipline).

## Impact

- Affected specs: `engine-bump-pr-body` (the composer gains a reader/writer consumer on already-open PRs).
- Affected code: new `scripts/engine_bump_restamp.py`, new `engine-bump-restamp` target in `mk/engines.mk`,
  new `tests/test_engine_bump_restamp.py`, `docs/changes.d/` fragment + `agent-wiki/` entry.
- Pull requests #3029–#3035 bodies (host-side, through the seam) — no engine pin, params, Dockerfile or skill
  file changes in this lane.

## Not covered

- The next scheduled wave's live read (issue #3053) and the "next bump wave must show green" observation
  (issue #3061) — those resolve against a real wave, not against this re-stamp.

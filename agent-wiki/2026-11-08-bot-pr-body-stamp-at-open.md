# 2026-11-08 — a bot PR carries the AGENTS/BASE pair at OPEN (#2050)

**Issue:** [#2050](https://github.com/asimov-agent/llgenie/issues/2050) ·
**OpenSpec:** `ci-bot-pr-body-stamp-at-open` · **Related:** #792, #845, #1788, #1790, #2051, #2046

## What was measured

At `origin/main@cb6c56a9` (91,766 B / 1,363 l of `AGENTS.md`), five open bot PRs — #1696 `cbe99416`,
#1982 `ad924f7d`, #2039 `8eca264a`, #2043 `12d40761`, #2049 `e1ec9d9c` — were red on
`make check-pr-agents-line` alone: no `AGENTS:` line, no `BASE:` line, or a pair measured at a sha the
gate cannot reach. The `guard` job reds before the substantive matrix runs, so auto-merge stays deferred
and the PR looks blocked for a reason that has nothing to do with its diff.

By 23:08Z all six PRs carried a valid pair again — a person or a later pass fixed their bodies by hand.
That is exactly the shape of a control that is not enforced where it is needed: the pair was a step a leg
had to REMEMBER, and `make bot-preflight` only *warned* (or refused a `BODY=` it was handed). No producer
that composed a PR body ever called it.

Second measurement, same night: the fix-bot repaired #2051, edited its body (stamps + checklist) and
commented "Pushed as one commit with the owner PAT" — while the head never moved (`21fd7782`, no new
runs). The comment read `steps.loop.outcome`, not `steps.push.outputs.pushed`.

## What changed

- `scripts/bot_preflight.py`: `stamp_body(text, record)` (insert or REPLACE the pair, flush-left,
  adjacent, idempotent) and `resolve_record(root, base, refs)` (first resolvable ref of `origin/main`,
  `origin/HEAD`, `main`; refuses otherwise, naming #2050). `--stamp BODY [--out] [--refs]` is the CLI.
- `make bot-stamp-body` is the one seam every producer calls before `gh pr create` / `gh pr edit`.
- Producers stamp at open: `issue_implementer.render_pr_body` (its `record` is now REQUIRED; `open_pr`
  resolves it and refuses a body it cannot stand behind), `engine-bump.yml`, `registry-sync.yml`,
  `security_bot.pr_body`, `security_bumps.pr_body`.
- `fix-bot.yml`: a re-stamp step after the push (gated on a real pushed sha and a successful sync), and
  the outcome comment now distinguishes "pushed <sha>" from "green with no tree change — the head did not
  move".
- `tests/test_bot_stamp_body.py` (10 cases) and the two security fixtures now provision a real `main` +
  `origin/main`, so the stamp is measured rather than stubbed.

## Verification

- `tests/test_bot_stamp_body.py`: 10 passed. The gate is the judge — `pr_agents_line_findings` returns `[]`
  for the stamped body and `agents-line` for the same body without the pair (negative control), in a real
  bot-authored git repo.
- Targeted regression set (`test_bot_pr_body`, `test_issue_implementer`, `test_issue_bot_implement_leg`,
  `test_bot_preflight*`, `test_pr_hygiene_agents_line`, `test_fix_bot_sweep`,
  `test_security_bot`, `test_security_bumps`): all pass.
- `make openspec-validate NAME=ci-bot-pr-body-stamp-at-open` → valid.

## Decisions

- The gate is untouched. Weakening `check-pr-agents-line` would have turned five red PRs green and left
  the class of defect in place; the pair is written by the seam that opens the PR instead.
- `resolve_record` has NO `HEAD` default: on an agent branch `HEAD` is the branch tip, and a rulebook cited
  from there is not an ancestor of the base, which the gate reds. Refusing is the control.
- `fix-bot` re-stamps only when its sync landed (`steps.sync.outputs.rc == '0'`): a PR whose rebase
  conflicted keeps the base it opened with, and re-stamping there would claim a base it does not have.

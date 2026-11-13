# Publish carries the shape every gate owes (architecture bot)

## Why

The 6-hourly architecture refresh went red on its own gates. Measured on PR #2629
(issue #2628), ci-scope run `43386226859`:

```
[check-pr-closing] 1 violation(s): the squash commit text and the PR body close different
issues — the joined commit messages close (none). The pull request body closes #2628
```

The publish leg runs `git commit -m <title> -m <issue body>`: the commit text IS the draft
issue body — three `- [ ]` acceptance items, unticked, and no `closes #<issue>` line anywhere.
`render_pr` emits `Issue:/Fix:/Benefit:/Technical:` but omits the `## Acceptance criteria`
mirror, the `AGENTS:` line and the `BASE:` line. Since the hygiene gates landed on main
(commit-checkbox parity #2519, agents-line #792, the closing check), every refresh PR needs a
manual agent to amend the commit and hand-build the body blocks — measured on #2629, where the
fix was exactly that (amended commit carrying the closes line + ticked mirrors, hand-built AC
block + AGENTS/BASE lines, scope rerun rc=0).

## What Changes

- **`scripts/architecture_bot.py`** — the publish leg carries the shape the gates check:
  - `acceptance_items` (shared): the three criteria strings in ONE place, used by the issue
    body, the commit text and the PR body, so the three mirrors cannot drift.
  - `render_commit_body` (new): the bot commit message body is the run marker, a completion
    line, the ticked `- [x]` acceptance mirrors, and a `closes #<issue>` line — never the
    issue body dumped again.
  - `render_pr` adds a `## Acceptance criteria` section (ticked mirrors with `proven:` strings
    naming the publish commit's full sha), an `AGENTS: <sha> <bytes>b <lines>l` line, a
    `BASE: <full-sha> (== origin/main at open)` line, and keeps the closes line last.
  - `publish` reorders: draft issue → branch + pair + commit → edit the issue body so its
    acceptance items are ticked with proven strings naming the commit's sha → push → open the
    PR. CI only reads the mirrors after they are aligned, so `ci-scope` never sees an unticked
    body.
- **`tests/test_architecture_bot.py`** — extended in place: the commit text carries the closes
  line and the ticked mirrors with NO `- [ ]` box anywhere; the issue-body edit is recorded
  BEFORE `pr create`; every tick's proven names the publish commit's sha; the PR body carries
  the AC section, `AGENTS:` and `BASE:`.
- **`scripts/architecture_bot.py` docstring + `.github/workflows/architecture-bot.yml` header**
  — state the new publish shape.

## Impact

- Affected capability: `architecture-bot` (publish leg).
- Affected code: `scripts/architecture_bot.py`, `tests/test_architecture_bot.py`,
  `.github/workflows/architecture-bot.yml` (header comment only).
- Every future refresh PR passes `check-pr-closing`, commit-checkbox parity, `check-pr-hygiene`
  agents-line and the acceptance-form gate without a manual fix lane.

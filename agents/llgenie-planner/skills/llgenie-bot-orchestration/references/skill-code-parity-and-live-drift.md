# Skill↔code parity, and the live↔tree drift

Two independent drifts, two different homes, two different gates. Confusing them produces a gate that never reds.

## Drift A — live↔tree (host profile dir vs committed skills)

The live profile directory (`~/.hermes/profiles/<profile>/skills/`) is **not** the committed tree (`agents/<profile>/skills/` on `origin/main`). They diverge silently, in one direction: references get written live and never committed.

Measure before assuming anything:

```bash
LIVE=~/.hermes/profiles/<profile>/skills/<skill>
T=$(mktemp -d)
git archive origin/main agents/<profile>/skills/<skill> | tar -x -C "$T"
comm -23 <(ls "$LIVE/references" | sort) <(ls "$T/agents/<profile>/skills/<skill>/references" | sort)   # live-only
comm -13 <(ls "$LIVE/references" | sort) <(ls "$T/agents/<profile>/skills/<skill>/references" | sort)   # tree-only
rm -rf "$T"
```

- **`sync-agent-profile` in write mode truncates silently when live > tree.** It writes the tree over the live dir, so live-only files vanish with no error. Never run it in write mode as a "just in case" after measuring a live>tree gap; the gap is the finding, not the thing to erase. Fold live-only files by issue+PR, or file the fold as its own versioning issue.
- **A tree `SKILL.md` can be OVER the skill-writer's character limit, which makes it permanently unpatchable and turns the sync into a loaded gun.** `skill_manage` refuses any write to a `SKILL.md` above its limit (`SKILL.md content is N characters (limit: 100,000) — batch aborted, all touched skills rolled back`), so every intended fix to the tree copy fails while the live copy keeps moving. Measure BOTH sides before touching either:

```bash
wc -c ~/.hermes/profiles/<profile>/skills/<skill>/SKILL.md
git show origin/main:agents/<profile>/skills/<skill>/SKILL.md | wc -c
```

  If tree > limit and live < limit, a write-mode sync replaces the corrected live copy with the over-limit tree copy **and drops every live-only reference** — reverting the fix and re-orphaning the lessons in one command. The remedy is the same slimming that fixed live: move the largest inline sections into `references/<topic>.md`, leave a summary plus a pointer to each, land that in the tree by issue+PR. Whenever a `skill_manage` patch bounces on the size limit, treat it as a **tree-copy defect to file**, not a retry to grind — and never "fix" it by deleting content the limit merely made awkward to edit.
- A live-only reference is invisible to every lane that reads the repo, and it is the copy *you* obey — so a wrong live-only reference is worse than none.

## Drift B — skill↔code (documented mechanism vs actual behaviour)

A reference that explains a mechanism ("a head whose marker went stale is skipped by every cron run") goes stale the moment the code changes, in either direction:

- doc describes the bug as behaviour after the code fix → the next lane reads it, concludes "nothing will ever handle this", hand-merges or files a duplicate diagnosis;
- doc is right while the code is wrong → invisible until a PR sits green and unmerged.

**Rule: anchor every mechanism claim to the test id that proves it.** Write `(proven: tests/test_x.py::test_y)` in the reference and have a gate assert that test exists and passes, plus that every backticked code symbol still resolves. Anchor to *behaviour*, never to prose — a prose-only anchor reds on re-wording and teaches people to edit the doc to match a failing check.

`scripts/check_issue_body.py` is the existing model of "assert a documented shape against the code that renders it"; a skill↔code gate is the same pattern over markdown references.

## Filing the gate itself

The gate is a normal issue: two Makefile targets (`skill-parity` host read-only; `check-skill-code-parity` CI), each mutation-proven to fail on a deliberately broken anchor. Keep the live→tree fold **out of scope** — it is its own versioning issue; the gate only makes the drift visible.

## Issue-body shape (the gate you will hit while filing)

`scripts/issue_body.py::SECTIONS` is `("Problem", "Why it matters", "How we fix it", "Benefit", "Acceptance criteria", "Technical")`, with optional `Not covered` allowed anywhere between `Benefit` and `Technical`, and **`## Technical` last**. Criteria are written as `- [ ]` checkboxes a reviewer ticks.

`scripts/check_issue_body.py` takes `check --root <dir>` (it scans producer sources), **not a body file** — passing a path errors with `unrecognized arguments`. To validate a hand-written body, grep the headings and the unchecked-criterion count instead.

## Pitfall: distinguishing "missing" from "empty"

`git show origin/main:<path> | grep -q X` returns empty and exits clean-ish in a pipeline when the file does not exist, so "grep found nothing" cannot tell *stale content* from *no file*. Probe existence separately first:

```bash
git cat-file -e origin/main:<path> 2>/dev/null && echo EXISTS || echo MISSING
```

Without that probe you will write "the sentence is not on main" when the truth is "the file is not on main" — two different findings with two different remedies (edit vs commit).

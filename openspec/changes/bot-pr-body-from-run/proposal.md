# A bot PR's description is built from the run, not from a fixed string

## Why

`make issue-bot-open-pr` passed a hardcoded title and a placeholder footer:

```
python3 scripts/issue_implementer.py open-pr … --title "issue-bot implementation" \
    --wants "Verification notes land on the PR as CI runs it."
```

and `open_pr()` composed `f"{body}\n\ncloses #{num}\n{wants}"` with `body=""`. Every bot PR therefore
opened with the same three lines — no issue, no fix, no benefit, no files touched — while carrying
`closes #<n>`:

```
(blank)

closes #407
Verification notes land on the PR as CI runs it.
```

PR #424 is that text over a one-line diff. `make check-pr-hygiene` did not catch it because it inspects
a producer's **source**: the argument it reads is the f-string `f"{body}\n\ncloses #{num}\n{wants}"`,
which is neither empty nor in `PLACEHOLDERS`. So the gate that exists for this class was blind to the
one producer that renders its body at runtime (issue #429).

## What Changes

- **`scripts/issue_implementer.py`** — `open_pr()` takes a **body file**, not a string:
  - `pr_title(title, num)` derives the subject from the issue's own title (kept when it is already a
    typed Conventional Commit, else prefix `feat: `) and appends `(#<n>)` — never
    `issue-bot implementation`;
  - `render_pr_body(text, num, diffstat)` refuses, naming what is wrong, unless the text carries
    non-empty `Issue:` / `Fix:` / `Benefit:` / `Technical:` parts and names `#<num>`, then appends the
    pushed commit's own file list (`git show --stat`) and the `closes #<n>` marker;
  - a missing body file is refused **before** any `gh` call, so a PR whose description says nothing
    cannot exist.
- **`Makefile`** — `issue-bot-open-pr` passes `--body-file pr-body.md` (overridable with `BODY_FILE=`),
  and `_implement-issue` carries it as a rule: before it finishes, the agent writes `pr-body.md` with
  the four labelled parts, because the job builds the PR body from that file and refuses without it.
- **`.gitignore`** — `pr-body.md` is a run input, like `issue.md` and `triage.md`.
- **`tests/test_bot_pr_body.py` (new)** — the rendered check the hygiene scan could not be: a missing
  file refuses and never calls `gh`, a missing/empty part is named, a body that does not name the issue
  is refused, a real body carries the four parts + the file list + `closes #<n>` in order, the title is
  typed from the issue, the producer passes no fixed title and no `--wants`, the implementer prompt asks
  for the body, and `pr-body.md` is ignored by real git.
- **`README.md` + `agent-wiki/`** — the body contract.

## Impact

- A bot PR can no longer be opened with a description that says nothing: either the run wrote a real
  body or there is no PR.
- The reviewer reads the issue, the mechanism, the benefit, the files and the tests without opening the
  issue thread.
- The `--wants` placeholder and the hardcoded title are gone from the producer, so the defect cannot be
  reintroduced by editing a default.

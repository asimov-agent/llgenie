# A bot PR's description comes from the run

- Issue: [#429](https://github.com/asimov-agent/llgenie/issues/429)
- OpenSpec change: `bot-pr-body-from-run`
- Branch: `fix/bot-pr-body-from-run`

## What was wrong

`make issue-bot-open-pr` passed `--title "issue-bot implementation"` and
`--wants "Verification notes land on the PR as CI runs it."`, and `open_pr()` composed
`f"{body}\n\ncloses #{num}\n{wants}"` with `body=""`. Every bot PR opened with the same three lines and
no description, while carrying `closes #<n>` — PR #424 is that text over a one-line diff.
`make check-pr-hygiene` cannot see it: it reads the producer's source, where the body argument is the
f-string `f"{body}\n\ncloses …"`, neither empty nor a known placeholder.

## What changed

- `scripts/issue_implementer.py` — `pr_title()` (the issue's own typed subject, else `feat: `, plus
  `(#<n>)`), `render_pr_body()` (requires non-empty `Issue:`/`Fix:`/`Benefit:`/`Technical:` and a
  reference to `#<n>`, appends `git show --stat` and `closes #<n>`), `diffstat()`, and `open_pr()`
  taking a **body file** and refusing a missing/thin one **before** any `gh` call.
- `Makefile` — `issue-bot-open-pr` passes `--body-file pr-body.md` (`BODY_FILE=` to override), no
  `--title`/`--wants`; `_implement-issue` carries a rule telling the agent to write `pr-body.md` with
  the four parts before it finishes.
- `.gitignore` — `pr-body.md` is a run input.
- `tests/test_bot_pr_body.py` — 8 cases, the rendered check: refusal without a file (and no `gh` call),
  a missing part, an empty part, a body that names no issue, a real body's four parts + file list +
  `closes`, the typed title, the producer's argv, the prompt, and real `git check-ignore`.
- `tests/test_issue_implementer.py` — the two `open_pr` call sites updated to the body-file signature.
- `README.md` — the body contract.

## Verified

Real runs of the command, on this branch:

```
$ python3 scripts/issue_implementer.py open-pr --repo o/r --issue 429 --branch b --title "fix(x): y" --body-file /tmp/absent.md
[issue-implementer] /tmp/absent.md is missing: the implement step must write the PR body
(Issue:, Fix:, Benefit:, Technical:) at the repo root; refusing to open a PR whose description says
nothing (issue #429)                                    exit=1

$ … --body-file /tmp/thin.md          # Issue/Fix/Technical, no Benefit
[issue-implementer] pr-body.md cannot become a PR body: `Benefit:` is missing        exit=1

$ … --body-file /tmp/good-body.md --dry
[issue-implementer] would open fix(issue-bot): a bot PR body comes from the run (#429) from b -> main
Issue: #429 — … / Fix: … / Benefit: … / Technical: …
Files changed:
``` … 11 files changed, 760 insertions(+) … ```
closes #429                                            exit=0
```

- `pytest tests/test_bot_pr_body.py tests/test_issue_implementer.py` → 38 passed.
- `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`,
  `make openspec-validate NAME=bot-pr-body-from-run` — green.

## Notes

- `pr-body.md` joins `.gitignore`; the roster check in `tests/test_bot_scratch_ignored.py` (#427) accepts
  a name a producer writes, so the two changes do not have to land together.
- The rendered check lives in the unit suite because a source scan cannot judge a runtime-built body —
  that is exactly why `check-pr-hygiene` was green on #424.

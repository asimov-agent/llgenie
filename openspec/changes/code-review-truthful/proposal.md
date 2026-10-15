# The code-review bot's report must equal the findings it acts on (issue #307)

**Issue:** [#307](https://github.com/asimov-agent/llgenie/issues/307)
**Capability:** `code-review-truthfulness`

## Why

`scripts/code_review.py` is the repo's deterministic reviewer: its whole output is one issue per
finding (#269). Two defects make that report untrustworthy, measured by exercising
`code-review-bot.yml` for the first time.

**1. A `secrets.X` in a COMMENT is filed as an undefined secret.** `check_secrets_not_defined` scans
the RAW workflow text (`SECRET_REF.findall(_read(wf))`), while every other check reads the
comment-stripped `run:` blocks (`_steps`). So a documentation line that names `secrets.X` becomes a
finding:

```
$ python3 scripts/code_review.py scan --repo asimov-agent/llgenie
- ci: the workflows read secrets.X, which the repo does not define     <-- BOGUS
$ grep -n 'secrets\.X' .github/workflows/rebase-bot.yml
93:        # `${{ secrets.X }}` inside a `run:` block is a value in a log waiting to happen).
```

On the next non-dry run the filer opens an issue claiming `secrets.X` is missing. `X` is not a
secret any workflow reads — the finding is false.

**2. The `scan` step runs tokenless, so its report is not the filer's report.** The "Scan the tree
and the pipelines" step runs `make code-review-scan` with no `GH_TOKEN`, while the filer step carries
`GH_TOKEN: ${{ secrets.BUMP_TOKEN || github.token }}`. Both call the same `findings()`, so the scan
cannot read the two API-backed checks and prints `no findings` while the filer (same tree, with
token) files 3 — measured in run
[38825474696](https://github.com/asimov-agent/llgenie/actions/runs/38825474696). The workflow header
calls the scan "the record of what the checks saw … the evidence the issues will quote", and the
summary tells a reviewer to "see the scan step above"; the two halves contradicting each other is the
failure shape.

## What Changes

- **`scripts/code_review.py`** — `check_secrets_not_defined` reads every workflow with comments
  stripped (full-line `#` comments removed) before matching `secrets.X`, so a documented example is
  never a reference. A `secrets.X` on a real `env:`/`with:` line is still a finding.
- **`.github/workflows/code-review-bot.yml`** — the `scan` step carries the same
  `GH_TOKEN: ${{ secrets.BUMP_TOKEN || github.token }}` as the filer, so `make code-review-scan` and
  `make code-review-file` report the same findings.
- **`tests/test_code_review.py`** — a commented `secrets.X` yields no finding, a real `secrets.X`
  still does, and the workflow's scan step carries `GH_TOKEN`.

## Impact

The bot stops filing a bogus `secrets-not-defined/X` issue. The two real findings its checks already
produce on `main` (`issue-refiner.yml` reads `secrets.OPENROUTER_API_KEY` / `secrets.OPENCODE_API_KEY`,
neither of which the repo defines) stay — those are separate, legitimate gaps.

## Not covered

- The two real `secrets-not-defined` findings against `issue-refiner.yml` — filed/actioned separately,
  they are not this bug.
- `#305` (the inline-script check only inspects the last `run:` block) — separate defect, separate fix.

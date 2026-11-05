# Filing an issue in the llgenie tree (six-section shape gate)

Load before you `gh issue create` for a defect this lane found on the host. The repo has a machine
shape gate on issue bodies and a red one reads like an unrelated docs failure.

## The six required sections, in order

```
## Problem                what is wrong, measured
## Why it matters         the consequence of leaving it
## How we fix it          numbered, plain language, no file paths
## Benefit                what the reader gets once fixed
## Acceptance criteria    one `- [ ]` per provable outcome
## Technical              LAST and only here: files, targets, tests, gates, measured numbers
```

`Technical` must be the final section. The PR-hygiene gate maps these to the PR body keys
`Issue:` / `Fix:` / `Benefit:` / `Technical:`.

## Validate the body against the repo's own gate BEFORE creating the issue

The module is `scripts/issue_body.py`; import the functions that exist (`headings`, `missing`) — there
is no `problems()`.

```bash
cd <worktree> && python3 -c "
import sys,json; sys.path.insert(0,'scripts')
from issue_body import headings, missing
body=open('/tmp/issue-body.md').read()
print('headings:', json.dumps(headings(body)))
print('missing:',  json.dumps(missing(body)))
"
```

Green is `missing: []` with the six headings in order. Fix the body, not the gate.

## Create, label, and claim in one pass

```bash
gh issue create --repo asimov-agent/llgenie \
  --title '<area>: <symptom> — <gate that reds>' \
  --body-file /tmp/issue-body.md --label bug,agent:implement
```

Then read it back (`gh issue view <n> --json number,state,labels`) and post a claim comment carrying the
**measured** evidence: the numbers you measured, the command that reproduced the failure, and the
`check-*` verdict. Bookend it later with the resolving sha/run — an issue with a start comment and no
finish comment is an abandoned claim.

## Never fabricate the number

Fragment filenames, `CHANGES.md` rows and commit subjects embed `#NNN`; if the issue does not exist yet,
file it FIRST and name files from the real number. Never quote a guessed number in a body or subject.

## Ownership note belongs in `Technical`

Say which lane owns the remedy (a publish gap is the pipeline lane's; a launcher refresh is host-env;
params/tuning is this lane's). This lane files the issue and does not merge or arm anything for it.

# Proving a scan result (dispatch recipes)

Every claim about the scan is backed by one of these, never by reading a checks summary or a PR comment.

## Reproduce from the run itself

```bash
RID=$(gh run list --repo asimov-agent/llgenie --workflow security-scan.yml --event schedule \
  --limit 1 --json databaseId --jq '.[0].databaseId')
gh run view "$RID" --repo asimov-agent/llgenie --json jobs \
  --jq '.jobs[]|.name as $j|.steps[]|"\($j) :: \(.name) => \(.conclusion)"'
gh run download "$RID" --repo asimov-agent/llgenie --name security-reports --dir /tmp/sec
```

A step's log is the evidence, not its red cross: `gh api .../jobs/<id>/logs --allow-escape-sequences |
sed 's/\x1b\[[0-9;]*m//g'` yields the assertions or the verdict line in plain text.

## Replay the reports locally

```bash
cp /tmp/sec/* security-reports/            # gitignored; never committed
make security-issues-plan SLUG=asimov-agent/llgenie
make security-bumps-plan
```

The plan is also the test of *relevance*: if `security-bumps-plan` answers "every floor is already
satisfied" while the run still reports the advisory, the finding lives in a file the build does not install.

## Dispatch by what you are proving

```bash
# a fix's own shape: the last step must be the only red
gh workflow run security-scan.yml --repo asimov-agent/llgenie --ref <branch> -f tools=all -f enforce=full

# is the finding set gone on main: cannot red (pr_fail_on is empty), gives a run id
gh workflow run security-scan.yml --repo asimov-agent/llgenie --ref main -f tools=all -f enforce=report
```

- `--ref main` only means anything after the fixing PR lands: findings are read from the checked-out tree.
- Prefer a dispatch over squinting at a scheduled run's artifact: the dispatch carries a head sha and a run
  id, the scheduled run ties to neither.
- A disabled workflow cannot be dispatched at all — enable it first (see `fleet-pause-and-resume.md`).

## What a clean result looks like

```
[security-scan] OK (event=schedule, mode=full): 0 finding(s) recorded, none blocking
  (fail_on=['critical', 'high'], require_fix=True)
```

## Absence, not silence

- **"Clean" is a run, not an inference.** Only a scan at a named sha printing `0 finding(s)` supports it. A
  merged fix, a green CI, or an empty-looking tracker prove nothing about the tree.
- **A finding whose fix merged stays OPEN until a scan closes it.** `make security-issues` closes an issue
  through its `cleared` path only when a later scan stops reporting the advisory — so open findings plus a
  merged fix means no scan has run, not that the fix failed. Report it as **"fix merged, absence unproven"**
  and list the open advisories by severity.
- **Measure the gap; never estimate it.** Compute from the last run's `createdAt` in a command (a `python3
  -c` datetime subtraction); a guessed number understates an exposure and changes how urgently it escalates.
- **Hand over the re-enable proof.** While the workflow is disabled the only legitimate next step is the
  owner's: enable it, then dispatch `-f enforce=report` (cannot red), expect `0 finding(s)`, and watch the
  `cleared` path close the issues. State that plan instead of dispatching, forcing, or claiming clean.

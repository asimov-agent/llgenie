# Reproducing the acceptance / hygiene gates locally before a verdict

CI being red is not evidence a gate fails, and a container exit code is not evidence either. Classify
the red, then reproduce the component that matters. Order matters: classify → reproduce → only then
call a criterion failed.

## Classify an rc before you believe it

A non-zero rc from a container is one of three things, and only the first is a finding about the PR:

| rc | Tell in the log | Meaning | Action |
|----|-----------------|---------|--------|
| 1 | `[<gate>] FAILED: …` with a file/line or a violation count | real gate finding | report it, per-criterion |
| 2 | `docker: … not found`, nested `make` calling docker | tool absent inside the image (docker-in-docker) | run that component on the HOST |
| 2 | `UNREADABLE: git could not read this checkout` | git metadata missing in the mount | run on the host / full clone |

Read the component's own log lines before widening a verdict; `make lint` and `check-docs` aggregate
several components, so an rc of 2 hides which one spoke.

## `make lint` nests docker — run the components directly

`make lint` shells out to docker for parts of its work, so it cannot run inside the CI image. Run the
components themselves from the host, in the worktree, one per line so each rc is attributable:

```
python3 scripts/lint_linefeeds.py
python3 scripts/check_architecture_census.py check
python3 scripts/check_workflows.py check
python3 scripts/check_wiring.py check
make check-docs
```

## A worktree's `.git` is a FILE — census cannot read it through a bind mount

A `git worktree` has a `.git` file pointing at the parent repo's `worktrees/<name>` directory, not a
`.git/` directory with objects. Containerising only the worktree directory (`-v "$PWD":/repo`) gives
no access to that parent path, so census reports `UNREADABLE: git could not read this checkout` and
exits 2. That is a mount artifact, never a defect in the branch. Two legal fixes: run the census from
the host on the worktree (the `.git` file resolves there), or point the container at a full clone.

The SAME bind mount is fine for pytest — `llgenie/test:latest` + `-v "$PWD":/repo` is the right way to
prove a test fixture. Only git-metadata-reading gates (census, changes index) need the real repo.

## Feed the gate the body you are judging — PR body, not issue body

`check_pr_acceptance.py check --body-file <path>` grades whichever text it is handed. The issue body
and the PR body are different inputs, and an issue body can legitimately CONTAIN a closing keyword in
prose (a measured example, a quoted violation), so feeding the issue body produces a meaningless
verdict in either direction. Always:

```
gh api repos/<o>/<r>/pulls/<n> --jq .body > prbody.md   # the PR under review
python3 scripts/check_pr_acceptance.py check --body-file prbody.md
```

If the rc surprises you, check which file you passed before re-reading the gate's logic.

## The gate log is often the fix's own proof

When the change under review alters what a gate PRINTS, the guard job log at head is direct evidence:
the violation lines name the linked issue in `title`/`where`/`evidence`, or the placeholder is gone from
`closes #<n>`. Quote those log lines in the review instead of arguing the code reads correctly — the log
is the behaviour at the head being judged.

## Overall run failure ≠ your gate

After a rerun clears one step, the run's `conclusion` can stay `failure` because a DIFFERENT step or
leg is red. Never form the verdict off the run conclusion; enumerate the failing steps:

```
gh api repos/<o>/<r>/actions/runs/<run>/jobs?per_page=100 \
  --jq '.jobs[]|{name,conclusion,failed:[.steps[]|select(.conclusion=="failure")|.name]}'
```

A guard whose `check-pr-acceptance` step reads `success` while the run is red means the acceptance red
is cleared and something else (commonly `check-pr-base`) is now the only red — see
`references/acceptance-hold-release.md` for the unmask and how to route it.

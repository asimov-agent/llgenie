# Evidence and run verification

How to make a claim that survives an owner fact-check, and how to actually run the
gate a change has to pass. Every pilot in this file exists because a plausible
number was believed without being fetched.

## Cite only ids you fetched this turn

- A run id, job id or commit sha quoted in a comment is a hard assertion. Read it
  back from the API **in the same turn you write it**:
  ```
  gh api repos/<owner>/<repo>/actions/runs/<id> --jq '{status,conclusion,head_sha,updated_at}'
  gh api repos/<owner>/<repo>/actions/runs/<id>/jobs --jq '.jobs[]|{id,status,conclusion,name,steps}'
  ```
- Deriving a plausible-looking number from a pattern ("the next run in the sequence
  would be …") is **fabrication**, not evidence. If you cannot fetch it, write
  `unverified` — never a guessed id. One invented id retroactively invalidates every
  other true claim in the same comment and costs a public retraction.
- When you discover you cited an unverified value, own it plainly in a follow-up
  comment (id + what was wrong) and withdraw it; do not bury it.
- **Compare a sha against its full string or `startswith`, never `head[:9] == "<8-char>"`.** A 9-char slice
  compared to an 8-char literal is `False` for a perfectly matching head and reads as "the push did not
  land", costing a needless re-check. Use `head.startswith(short)` or compare the whole sha.

## A frozen `updatedAt` is not a stall

GitHub does **not** bump a run's `updatedAt` while a job step is mid-execution. A run
whose `updated_at` has not moved for 10+ minutes may be perfectly healthy inside a long
step (a `make test-unit-network` live-sync step legitimately runs ~16 min). Before you
call a run stuck:

```
gh api repos/<owner>/<repo>/actions/runs/<id>/jobs \
  --jq '.jobs[]|{name,status,current_step:.steps[-1].name,started:.steps[-1].started_at,completed:.steps[-1].completed_at}'
```

If the step has `started_at` set and `completed_at: null`, it is **running**, not stuck.
Only a step with no forward progress and no new `started_at` across repeated polls is
stalled evidence. Retract a premature "stalled" characterization explicitly.

## Real test, not a re-implementation

The task-relative verification is the **actual pytest node id** that the CI gate runs,
not an ad-hoc driver that re-derives its assertions. A hand-written proof proves your
mental model; it does not prove the acceptance gate and does not satisfy a reviewer or
the task guard. Run the real case at the committed head and report its true exit status:

```
<venv>/bin/python3 -m pytest tests/<file>.py::<test> -m network -p no:cacheprovider -q --tb=short
```

Pick node ids precisely; `-k` selectors can match hermetic duplicates you did not mean
to run.

## Running the long live-sync test

- Use the **explicit venv python** (the path under the installs/environments tree); the
  Hermes tools python has no `pytest` and exits 2 with no output.
- A foreground wrapper caps at ~420 s and will kill the ~16-min sync mid-run — launch it
  as a **durable background job** (`notify: true`, generous timeout) that writes its
  result to a JSON file, then read that file back. A degraded channel swallows stdout;
  file-on-disk is the only reliable channel.
- `pytest` exiting 2 with **zero output** means it aborted at startup (import/collection),
  not that the test failed — capture stderr to a file and read it.

## Verify a commit landed before opening the PR

`gh pr create` failing with `No commits between main and <branch>` means the commit
**never landed** (commonly a malformed commit command), not a PR-config problem. Check
`git log <base>..<branch> --oneline` and confirm the branch is ahead by your commit
before retrying.

## Registry ranking sanity

A tps figure is only valid evidence for the model it was measured on. A PrismML-fork
("Bonsai") repack measurement attached to a **dense** model must not be offered as that
model's engine — gate PrismML/tensor-fork engines on `is_ternary(model)` (or equivalent
tensor-type check), never on the mere presence of a tps number. Ranking a dense model
should surface a stock engine whose measurement belongs to the same model.

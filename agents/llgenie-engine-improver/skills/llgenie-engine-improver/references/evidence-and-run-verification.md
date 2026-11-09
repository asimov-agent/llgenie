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

## A write that printed nothing did not happen

`gh issue comment --body-file <f>` can exit **0 with empty stdout and post nothing**.
An exit code is not the fact: never report a comment, label, or edit as posted until you
have read the resource back.

```
gh api repos/<o>/<r>/issues/<n>/comments --jq '[.[].id] | max'   # id, not count alone
gh api repos/<o>/<r>/issues/<n>/comments --jq '[.[]|{id,created_at}]|max_by(.created_at)'
```

If the max id is still the one you saw before the write, the write did not land. Re-post
the body through the API with a file reference, then read the id back again:

```
gh api repos/<o>/<r>/issues/<n>/comments -F "body=@/tmp/<body>.md" --jq '{id,created_at}'
```

Same rule for PR comments, labels and review-requests: read the field back. Note
`gh api` has no `-o` flag — redirect stdout to a file (`> out.json`) and parse that,
rather than inventing a flag and losing the response.

## Acceptance = the failure signature is absent from every red job's log

An overall run `conclusion` is a verdict, not a cause. When a matrix run is red but your
fix targets one specific failure mode, the acceptance question is *"is my failure mode
still present anywhere?"*, not *"is the run green?"*:

1. `gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '.jobs[]|select(.conclusion=="failure")|{id,name}'`
   — enumerate the red cells.
2. Pull each job's **own** log: `gh api repos/<o>/<r>/actions/jobs/<job_id>/logs`.
   A jq'd blob fetch returning `BlobNotFound` or 0 bytes is a wrong endpoint, not a
   missing log; drop the `--jq` and fetch the raw job-log text.
3. Grep every log for the **signature tokens of the failure you fixed** (scope/pull-denied/
   manifest-not-found strings, a specific step name, a specific rc). Report the hit count
   across all red jobs.
4. Classify each red cell by its own cause. Seam/your-fix causes vs unrelated causes
   (runner disk exhaustion, a skip that printed but was not honoured, a serve-timeout
   after a successful build, a killed step). "0 signature hits across N red cells" is a
   real, citable acceptance result; "the matrix is red" alone is not a refutation, and
   "the matrix is red so my fix failed" is a wrong claim when no cell shows your signature.

Report both facts separately in one comment: acceptance of the fix (with the signature
scan), and the non-target reds as findings routed to their owners — never silently
de-scoped, and never blurred into the same verdict.

## Prove a NEW gate's decision by importing the module and driving it against LIVE data

A gate that decides on live API state (a pre-poll that skips a wait when a producer cell is already red, a selector that reads a run's conclusions) cannot be accepted on unit tests alone — the stubs prove the branch logic, not that the live query returns what you think. Prove the whole path without a fake bench:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("m", "scripts/<gate>.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m._producer_cell_conclusions("<owner>/<repo>", "<branch>", "<engine>", GH))  # real gh, real cells
```

- Call the internal query against the REAL repo/branch and quote what it returns for both a red-involved engine and a green one — the green case is what proves you did not weaken the gate (red ⇒ skip, green ⇒ still polls).
- Exercise it on the branch the gate actually targets (the PR head), not only `main`; the producer's cell conclusions differ per branch and the branch is the real input.
- Keep the gh binary path explicit (the mise shim path) — a `gh` subprocess launched from a bare `subprocess.run(["gh", …])` inside an interpreter sandbox can return empty stdout while the same call via the terminal tool works; an empty result is not proof the API has no runs, it means re-run the query through the working channel before concluding.

## Registry ranking sanity

A tps figure is only valid evidence for the model it was measured on. A PrismML-fork
("Bonsai") repack measurement attached to a **dense** model must not be offered as that
model's engine — gate PrismML/tensor-fork engines on `is_ternary(model)` (or equivalent
tensor-type check), never on the mere presence of a tps number. Ranking a dense model
should surface a stock engine whose measurement belongs to the same model.

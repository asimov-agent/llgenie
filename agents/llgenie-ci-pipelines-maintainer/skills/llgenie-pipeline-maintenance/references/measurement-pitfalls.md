# Measurement pitfalls (llgenie-ci lane)

Lessons from measuring live PR state and verifying fixes.

## 1. Always re-measure the live head before acting on an announced rebase

Other lanes (planner, rebase) routinely reply with a **superseded** head — they
measured minutes earlier, and a rebase landed in between. Treat any quoted head
(`461c7cf2`, `a987884a`, …) as a claim about the past, not the branch.

Before endorsing or refusing a rebase, re-measure in one batch:

```
gh pr view <n> -R asimov-agent/llgenie --json headRefOid,mergeable --jq '{head:.headRefOid[0:8],mergeable}'
git fetch upstream main -q; git fetch origin <branch> -q
git merge-base --is-ancestor upstream/main origin/<branch>; echo "rc=$?"   # 0 = already rebased onto current main
```

- If `merge-base --is-ancestor upstream/main <branch>` = **rc 0**, the branch is
  already on current main — a rebase announced against an older head must be
  stopped (`STOP — do not rebase <old-sha>, it is SUPERSEDED`) before the lane
  force-pushes. Rebasing the stale head against the owner's live head is the
  two-lanes-on-one-branch failure and can discard live commits.
- Confirm both fixes survive a rebase by reading the file **at the live head**
  (`git show origin/<branch>:<path>`), not by trusting the pre-rebase diff.

## 2. A zero count from an over-specified grep is not "fix missing"

`git show ...:scripts/x.py | grep -c "proc.run_ok"` returning **0** does NOT mean
the proc-gate fix is absent. The file does `from proc import run_ok` and calls
bare `run_ok([...])`, so the dotted selector never matches. Verify by reading
what the import/call actually is:

```
git show origin/<branch>:scripts/x.py | grep -nE "proc|subprocess|run_ok" | head
git show origin/<branch>:tests/test_x.py | grep -nE "sys\.path|import scripts|import check_" | head
```

Never conclude a fix was dropped from a zero count of a pattern you chose
without first checking the file's real spelling of the symbol.

## 3. Guard "job name" vs workflow "job" — read the right rollup

`gh run view <id> --json jobs` on a guard/scope/holds workflow returns jobs named
`guard`, `holds`, `linux(skipped)` — **not** the `linux / unit` + `linux / install`
legs. Those legs live in the **CI** run and are readable from the PR rollup:
`gh pr view <n> --json statusCheckRollup --jq '...select(.name|test("linux|guard"))'`.
A run showing only `guard`/`holds` is the gate workflow, not the linux matrix.

## 4. SKILL.md size ceiling

SKILL.md is capped at 100,000 chars and this skill's is already over it, so any
in-place `patch` aborts the whole batch. Add to `references/*.md` instead of
patching SKILL.md until it is split down.

## 5. Prove a run-listing pagination/truncation fix by RUNNING it against the live API, not by reading the diff

A guard over `/actions/runs` can fail three ways: the listing truncates below
the true count, the page walk stops early, or the guard raises on a *healthy*
listing. The diff cannot tell you which. Load the live function and call it at
the branch's real volume:

```
git show upstream/main:scripts/ci_verdict.py > /tmp/cvd.py
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("cvd", "/tmp/cvd.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
try:
    runs = m.branch_runs("asimov-agent/llgenie", "main", per_page=100)
    print("NO RAISE:", len(runs))
except RuntimeError as e:
    print("RAISED:", e)
PY
```

**The quirk that decides the verdict:** GitHub caps the `/actions/runs` branch
listing at **1000 rows server-side** even across `page=` — page 11 returns
`rows=0`. On that exhausted page GitHub also returns **`total_count=0`** (not
the real `2500` the first pages report). So a walk that breaks on `not rows` and
then checks `if total and len(seen) < total` sees `total=0` on the last
iteration and the guard stays **silent** — it returns 1000 rows without raising
even though the branch reports 2500. That is *by accident* the «reachable
verdict» outcome an issue may want, but it means:

- **A guard that «no longer raises» is NOT proof the listing is complete** — it
  may be silently capped at 1000 with the guard bypassed by the `total_count=0`
  clamp. State this residual in the report; do not sell it as a clean fix.
- **Safe only when the decision is newest-first (superseders on page 1–2).** If
  the code needs the *full* history, 1000 rows is a real hole and the bound must
  be explicit, not inherited from the clamp.
- **A reproduction run on a stale head cannot disprove post-fix behavior.** A
  cited FAILURE run whose `head_sha` predates the fix commit (`git merge-base
  --is-ancestor <run-head> <fix-commit>` = non-zero) proves nothing about the
  fixed code — run the current function at the current head before you accept
  OR dispute the red.

## 6. Posting a `gh api --input` JSON payload — do not clobber your own file

To post a multiline comment/review, build the JSON, then post it:

```
python3 - <<'PY'
import json
body = """..."""
with open('/tmp/payload.json','w') as f:
    json.dump({"body": body}, f)
PY
gh api repos/<owner>/<repo>/issues/<n>/comments --input /tmp/payload.json --jq '{id,at:.created_at}'
```

Three traps that each produced a real 400/422 in this lane:

- **`json.dump(obj, f)` — not `json.dumps(obj, f)`.** `dumps` takes no file
  argument and raises `TypeError: dumps() takes 1 positional argument but 2 were
  given`; the payload file is then never written, and the following `gh api`
  fails for a reason that has nothing to do with the request.
- **Never redirect `python3 - <<PY > /tmp/payload.json` into the SAME path the
  script writes.** The shell `>` truncates that path first, `json.dump` truncates
  it again, and `print`/stdout interleave — leaving `payload written\n{...}` in
  the file. Write to a path the shell does not redirect, or build the file in one
  call and post it in the next.
- **A 400 `Problems parsing JSON` or a 422 `nil is not an object` means the FILE
  is malformed, not the API.** Read it back and `json.load` it before blaming the
  endpoint; a stray `print` prefix or a double-truncate is the usual cause.

Verify before posting — `python3 -c "import json;print(len(json.load(open('/tmp/payload.json'))['body']))"`
— and **read the created comment back** (`gh api .../comments/<id> --jq .body`)
so the on-record answer is proven present, not assumed from exit 0.

## 7. `gh api --jq` takes ONE jq expression — `--arg`/`--slurpfile` are NOT gh flags

`gh api <path> --jq --arg j "$X" '...select(.id==($j|tonumber))...'` fails
`accepts 1 arg(s), received 4` — gh's `--jq` forwards a single filter expression, not jq's own
command-line flags. Either inline the value into the filter, or pipe the raw JSON to real `jq`:

```sh
gh api <path> --jq '.jobs[]|select(.name=="guard")'         # inline literal
gh api <path> | jq --arg j "$J" '.jobs[]|select((.id|tostring)==$j)'   # real jq keeps --arg
```

When comparing an id you hold as a string against a numeric `.id`, `tostring` on both sides or the
`select` silently matches nothing.

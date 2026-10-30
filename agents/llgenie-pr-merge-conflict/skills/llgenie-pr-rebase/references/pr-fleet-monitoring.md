# Monitoring a PR fleet without lying about it

Depth for the rebase lane's watches: how to describe a PR board so that every sentence is true at the
moment it is printed. The failure this prevents is not a missed alert — it is a *confident wrong status*
("five green", "five red", "nothing to do") that sends a human to merge or wait on the wrong thing.

## The four states of a check, and the two of a PR

Per check run, read `conclusion` from the API — never the rendered column:

| conclusion | means | never say |
|---|---|---|
| `success` / `skipped` | settled and fine | — |
| `failure` | red, real verdict | "flaky" without evidence |
| `cancelled` | **not yet**: superseded by a newer run (`cancel-in-progress`), or killed by a capacity sweep | "failing", "broken" |
| `null` + `status != completed` | running/queued | "done" |

`gh pr checks` renders `cancelled` as `fail`. Quoting that column as a failure count is how five
innocent PRs get called red, and — inverted — how template-named checks that never ran get waved through.

Per PR, two different readiness facts, and they answer different questions. Keep them apart in every
report, because a bot rule and a human status line are not the same claim:

- **bot-green** — `mergeable == MERGEABLE` **and** `mergeStateStatus == CLEAN` **and** every run on the
  current head settled, none cancelled, none failed. This is the only state a merge bot may act on.
- **owner-ready** — all of the above except the `CLEAN` requirement. Every check is green; the merge
  state is `BLOCKED` / `REVIEW_REQUIRED`, so a human's approval is the missing step. Calling this "not
  green" is false for the person who can merge it.
- **stuck-cancelled** — the newest run on that head ended `cancelled` with `attempt >= 2`. One
  cancellation is ordinary; a *second* means the retry was cancelled too and no verdict is coming
  however long anyone waits. Nothing else alerts on "still cancelled", which is why it needs its own line.

## Silence is a sentence, so define what it means

A delta watch that prints only transitions costs nothing when quiet — and its quiet is easy to misread.
Every watch's documentation must state its silence's meaning. For a green/red delta watch:

> silence means "no verdict changed", **not** "all healthy".

A board with half its PRs sitting cancelled produces no alerts and no green either. Put the headline
count in the human report and let the watch carry only transitions.

## Two designs that make "alert only on a transition" structural

1. **Monitor-gated agent** (`monitor` = deterministic script). The scheduler hashes the script's stdout
   and skips the agent run entirely when the bytes are unchanged: quiet hour = no LLM run, no delivery.
   Requirements: no timestamps, no state file, byte-identical output for identical input. First tick is
   always a baseline, and a forced/direct run **bypasses** the gate — so only a scheduled tick proves
   suppression. Read the proof out of the execution ledger (`source=builtin`, `delivery_outcome=suppressed`)
   against a direct run that delivered (`source=direct`); the contrast is the evidence, not either row alone.
2. **`no_agent` script job**. The script's stdout *is* the delivery, so empty stdout sends nothing and
   costs no model call. Right shape for pure reporting (deltas, tallies); wrong shape for anything
   needing judgement.

The detector must print a hard error (never "nothing conflicting") when the API read fails, or the
watch has a silent blind spot that reads as an all-clear.

## Query per commit, never from a window

A repo-wide run list (`gh run list --limit N`) is not a stable source for per-PR facts: after a burst of
new runs, an older PR's retry scrolls out of the window and the fact reads as absent — measured, a PR
sitting at `attempt=2 cancelled` reported as "not stuck" from a 100-run window.

Use the exact commit: `gh run list --repo <r> --commit <sha> --limit 1 --json attempt,conclusion`, and
`gh api repos/<r>/commits/<sha>/check-runs` for conclusions. Anchor every number to the head sha you
just read, because a new push invalidates all earlier counts — including ones you printed yourself.

## Rules for a watcher's own prompt

- A quiet pass is a legitimate completion: the job's task is to detect, not to change the repo. When
  nothing moved, report the measured state in one line and stop. Never invent work to satisfy a progress
  or completion check; say the check is unsatisfiable and stop.
- One rebaser at a time, and say which regime produced a report. When an in-repo automation owns the job
  again, the host watch degrades to alert-only and must say so explicitly, with the mode and the
  fix's merge state as separate fields so a stale alert stays honest.
- Derive the review order from measured state (failure-free and cancelled-free, ranked by unsettled
  check count), never copy an order out of a previous report — a remembered order lists PRs whose runs
  were cancelled an hour ago.
- Rejected `--force-with-lease` means another actor moved the branch: re-fetch, check whether it is
  already resolved, report and stop. Never escalate to a bare `--force`.

## A state-file delta watch must timestamp its lines
The two designs above make opposite demands, and mixing them is a real bug:
| design | dedupe mechanism | timestamps in stdout |
| monitor-gated agent | hash of stdout must be byte-identical | **forbidden** — a timestamp changes the bytes and defeats suppression |
| `no_agent` + state file | state file diffs the previous measurement | **required** — nothing else dates the output |
A `no_agent` job's delivery can arrive **hours late** (a `queue_full` queue, a retry, a resumed host) while the text still reads exactly like a fresh alarm. Answering it as live is expensive: it means re-measuring PRs that may have merged since. Stamp every emitted line with the measurement time so staleness is self-evident rather than inferable:
```
NEW-FAILURE     #101 @abcdef12  linux / unit   [measured 22:58:26Z]
```
Diagnose a suspicious alert in this order, cheapest first:
1. `gh api repos/<o>/<r>/pulls/<n> --jq .state` — closed means it is not a job at all.
2. `git merge-base --is-ancestor <quoted-sha> origin/main` — a head from superseded history cannot be rebased even if the PR is open.
3. the job's own `last_delivery_error` in the profile's `cron/jobs.json` — a `queue_full` delivery failure explains a late message with no measurement change.
Then re-run the reporter by hand and report what it measures **now**; never relay the delivered text. After a long delivery gap, re-baseline the state file rather than trusting the diff.
Prove a stamping change by re-baselining the state file (clear the recorded failures so real ones read as NEW), running the reporter, confirming the stamp appears, then restoring the baseline.

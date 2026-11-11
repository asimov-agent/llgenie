# Alarm design for a scheduled fleet

An alarm's job is to turn a silence into a red run. The failure mode of alarms is not being wrong —
it is being BLIND, and reading as health.

## The five silences, and which reader sees each

| state | what a "is it fresh?" check says | what sees it |
|---|---|---|
| job stuck `queued` | nothing (no conclusion exists) | age of the queued job, naming its runner label |
| run delivered, red | fresh — "delivered 2 min ago" | conclusion != success, INSIDE the freshness window |
| run green, produced nothing | healthy | the artifact: does the output exist / change? |
| a scheduled slot the platform DROPPED | no run at all — every run-reading check is blind | the AGE OF THE ARTIFACT |
| a pipeline red on every one of its own runs | healthy (its tab is not read) | a pipeline-level sweep of its own scheduled runs |

Write the table down before writing code: an alarm that covers one row certifies the other four.

## The artifact-age alarm

The only reader that survives a cron the platform never started.

- Measure the ARTIFACT's own timestamp — the one written INTO the filename by the producing job
  (`<name>-<YYYYMMDD>-<HHMMSS>.json`), never the file's mtime: a checkout sets mtime to the clone time,
  so a five-day-old artifact in a fresh clone looks seconds old. Pin that with a test that touches a
  stale file and asserts it is still reported stale.
- The window comes from the cadence, not from taste: two slots ~12 h apart need >12 h and <24 h, so one
  missed slot reds and a slow-but-present run does not. Derive it from the cron lines where you can.
- Report the newest SCHEDULED run beside the verdict. `none — no scheduled run exists` and `ran, green,
  produced nothing` need opposite follow-ups, and the artifact alone cannot tell them apart.
- A window shorter than N is not a failure (a pipeline added yesterday has not had N chances). Calling
  it red makes the alarm cry wolf on every new bot, and a noisy alarm gets muted.
- `gh` failing is a loud non-zero, never a clean bill of health. Same for "no artifact found" — nothing
  to measure is never health, and `--limit 0` is refused rather than vacuous.

## The pipeline-level alarm (red on every run)

- Derive the roster from the workflows themselves (a `schedule:`/`- cron:` line), so a pipeline added
  tomorrow is covered without editing the alarm. Tolerate a TRAILING COMMENT: `- cron: "7,37 * * * *"  #
  twice an hour` is the normal spelling, and a regex that misses it silently covers half the fleet.
- Read only `--event schedule` for the "red every time" question: a green manual run must not hide
  three red crons, and a red push run is a different alarm's business.
- Fail when the newest N are ALL bad; one success inside the window is enough to stay quiet.

## Roster derivation must not pass vacuously

Any check that derives what it examines needs three assertions, in this order:

1. **non-vacuity** — it found at least K members (an empty roster must FAIL, not pass);
2. **membership** — known members ARE present (name two or three real ones from the tree);
3. **exclusion** — a known NON-member is absent (a workflow with no cron in a cron sweep).

Expose the roster (`--list`) so the test reads the same value the sweep uses, instead of re-deriving it.

## Falsify every new guard before calling it a guard

The two ways a guard locks nothing, both silent:

- it compares a value to itself (`assert selected == {…for … in stage_lists()}` — always true);
- the fixture already satisfied the check before the change, so it passes on the base commit too.

Protocol: mutate ONE input the guard reads (a stage removed from `--only`, a t/s cell in the rendered
table, a workflow's env key) and confirm the exact failure line names the mutation. Restore the input.
Then run the same case against the base version (`git show origin/<base>:<file>`) — a case that passes
on both proves nothing.

## Corollary: an over-broad rule is a defect in the rule

If a new guard's first run lists a dozen pre-existing hits that all look idiomatic, tighten the rule to
the precise defect instead of rewriting a dozen files. A step-level `env:` key that the step's own
command line assigns the SAME value through (`REPO="$REPO"`) is one source, not a defect; a command
line assigning a DIFFERENT literal is the dead configuration. Encoding that distinction kept the guard
and left thirteen idiomatic steps alone.

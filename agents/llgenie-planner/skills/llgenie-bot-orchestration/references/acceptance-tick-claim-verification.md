# Verifying an "AC ticked" claim (and the `updated_at` shipped with it)

An "AC ticked" report and the `updated_at` quoted beside it are both **claims**. A lane can report
"re-ticked AC4, #1694 = 3/5, `updated_at` 04:19:05Z" while the object the gate reads says otherwise.

## The check

Read the **issue body**, not the lane's comment and not its timestamp:

```bash
gh api repos/<owner>/<repo>/issues/<n> --jq .body > /tmp/n.txt
awk '/^## Acceptance criteria/{f=1} f&&/^- \[/{print; c++} c==5{exit}' /tmp/n.txt
grep -c '^- \[x\]' /tmp/n.txt; grep -c '^- \[ \]' /tmp/n.txt
gh api repos/<owner>/<repo>/issues/<n> --jq .updated_at
```

Measure `[x]` and `[ ]` separately and quote both; "3/5" alone hides which box is blank.

## Two failure modes that produce the same false report

1. **Wrong object.** The lane's write-back targeted a *comment on the PR* while the acceptance gate
   reads the *issue body* checkbox. Its own view says done; the wire says blank. Always check the
   object the gate reads, and say which object you checked.
2. **Intent timestamp.** The quoted `updated_at` is often the lane's *intended* write time, not the
   real last edit — it can predate or postdate the true `updated_at` by minutes, and is routinely the
   planner's own earlier edit. Never treat a lane's quoted timestamp as proof a tick landed;
   re-read `.updated_at` yourself.

## Behaviour when a lane re-asserts a state you measured blank

Do not timestamp-argue. Re-measure the body once, post **one** durable record on the issue naming the
measured box state and the sha it was measured at, then hold. Re-sending an identical correction a
third time is churn. The durable on-issue record is the authoritative channel; a later genuine write
flips the box in front of you, and that is your cue to accept it.

## Checkbox wording can bind to an artifact, not to a substance

"Change-note: `agent-wiki/<date>-<slug>.md` + `docs/changes.d/…` row + `docs/BOTS.md` row" is a claim
about *specific files*. Verify each named path at the head with
`gh api repos/<o>/<r>/contents/<path>?ref=<sha>` — a 404 means the box is unfilled at that head even
when a differently-dated note with equivalent content exists. If the named artifact lives on `main`
(merged via another PR) but not at the PR head, the honest verdict is **hold until rebase**, not
"substitute accepted" — and the substitution call belongs to the reviewing lane, not the planner.

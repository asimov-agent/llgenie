# Proving a fleet-wide change actually landed

A change routed "to all lanes" is the highest-risk kind: the dispatch looks
successful, the board looks quiet, and the only thing between you and a false
report is how you verify. Three traps, all of which produce a confident wrong
answer.

## 1. A metric that was already true before your action proves nothing

The failure: dispatch a rule, then measure the condition the rule was meant to
produce, see it satisfied, and report success. If the condition pre-existed,
you have measured nothing and reported a green you did not cause.

**Measure the baseline BEFORE you dispatch, and quote before → after.** If you
cannot state a before value, you cannot claim an after value. "0 occurrences"
is only evidence when you can also say "it was N before".

**Check the target's mtime too.** A file whose content reads correct but whose
mtime predates your dispatch was not edited by anyone you dispatched. Content
can be accidentally correct; an mtime cannot be accidentally recent.

**Absence of the wrong thing is not presence of the right thing.** A file with
zero occurrences of a bad string and zero occurrences of the replacement has
simply never had either. Grep for the replacement as well, or the check passes
on an empty file.

## 2. A delivery process exiting non-zero is UNCONFIRMED — not delivered, not failed

A fan-out that waits for replies exits non-zero when the wait expires. The
message may have queued and delivered; the lanes may simply never have answered.
Neither outcome is recorded. A receipt carrying a delivery id and **no outcome
field** is pending, not proof.

**Never fill that gap with a metric that happens to read zero.** That is trap 1
reached by a different road, and it is the tempting one because it looks like
corroboration.

**Verify the artifact the lane was told to change**, per lane: its mtime after
the dispatch, and the presence of the thing you asked for. Or ask the lane
outright. Report it as unconfirmed until one of those answers.

## 3. Fleet-wide conventions live in shared skills copied per profile

Skills are not held in one place. A shared skill exists as a **global source
plus a real (not symlinked) copy inside every profile**. Consequences that
catch people:

- A **per-lane grep cannot see the shared cause**: each profile reports the same
  handful of hits and the fix looks like 13 unrelated problems.
- A **per-lane fix is 13 identical edits** that the next sync overwrites.
- **Fix the source and every copy in one sweep**, then count across all of them
  at once to verify.

Two carve-outs that are real, not pedantry:

- **`.archive/` is not instructions.** Retired skills inflate a whole-tree count
  into the thousands and teach the next reader to distrust the number. Exclude it.
  A raw whole-directory count is not a finding — scope the measurement before you
  publish it.
- **`scripts/*.py` is not prose.** A Python literal needs a real path or
  `pathlib.Path.home()`; rewriting it to `$HOME` yields a string that never
  expands. Change documentation and instruction text, leave code.

### The `$HOME` convention and its one carve-out

Instructions, docs and config examples use `$HOME`, never `/home/<user>`: every
lane shells through bash, so it resolves, and the absolute form encodes one
machine's account name in a public repository.

BUT anything **parsed rather than executed** must NOT use `$HOME`, because
nothing expands it there: systemd `ExecStart=` / `EnvironmentFile=` /
`WorkingDirectory=`, a crontab line outside a shell, a YAML/JSON value read by a
program. Those keep an absolute path or the native form (`%h` in systemd).
Rewriting a unit file to `$HOME` produces a path that silently never resolves —
worse than the literal it replaced. Say this explicitly whenever you broadcast
the convention, or a well-meaning sweep will break a working service.

## 4. One fleet's convention is not another fleet's instruction

Several fleets run on one host, each with its own planner. When a directive names
one fleet, editing another fleet's behaviour is peer-lane overreach even when the
same convention would obviously help it. **Report the occurrence; let that
fleet's own planner decide.**

## Reporting shape

State the measurement, its scope, and how many profiles/files it covers. "All
clean" without a scope is the sentence that hides trap 1. Name what is still
unconfirmed and who owes the confirmation.

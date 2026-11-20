# Spec Delta: sweep-record (rebase-sweep-record-2950)

## ADDED Requirements

### Requirement: The rebase sweep summary is posted by the lane to its record target

The rebase sweeper SHALL post, after every non-dry recorded lane pass, exactly ONE comment on the
record target issue whose first line is

`[rebase-sweep <UTC-stamp>] dispatched=<n> rebased=<n> deferred=<n>`

where `dispatched` counts the PRs the sweep picked this run (rebased + failed), `rebased` counts
completed rebases, and `deferred` counts the PRs left for the next run. Each deferred or
picked-but-failed PR SHALL get its own `- PR #<n>: <reason>` line in the same comment. The summary
is posted by `scripts/rebase_sweep_record.py` wired through
`make rebase-sweep-record REPO=… RECORD=<issue> DISPATCHED=… REBASED=… FAILED=… LINES=<file>`, and
the `rebase-bot` lane passes `RECORD=2652`.

#### Scenario: a recorded pass posts one summary comment

- **WHEN** a non-dry `rebase-bot` lane run finishes its drain loop with recorded deferrals and a
  failed pick
- **THEN** exactly one comment exists on the record issue with the fixed first line, the counts
  equal the lane's measured dispatched/rebased/failed numbers, and each named PR carries its own
  reason line

#### Scenario: an unrecorded or dry sweep posts nothing

- **WHEN** `rebase_sweep_record.py` runs with `--dry`, or the lane runs without a `RECORD` target
- **THEN** no comment is posted anywhere and the sweep's per-PR claim/done markers are unchanged

#### Scenario: a quiet pass records itself

- **WHEN** the sweep picked nothing (dispatched=0, rebased=0, deferred=0)
- **THEN** the record comment still posts, with zero counts and no per-PR lines

### Requirement: The sweep names its deferrals on stdout

`sweep()`'s already-computed `deferred` list SHALL be printed by `scripts/rebase_bot_sweep.py`
as one `deferred=#<n>` line per entry, so a consumer can count deferrals structurally instead of
parsing prose pass-over reasons. Existing reason lines and exit codes are unchanged.

#### Scenario: deferrals are greppable

- **WHEN** a sweep defers PRs (merge state unresolvable after re-queries)
- **THEN** stdout contains one `deferred=#<n>` line per deferred PR number

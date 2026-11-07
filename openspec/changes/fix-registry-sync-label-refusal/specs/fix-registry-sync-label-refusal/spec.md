# fix-registry-sync-label-refusal

## MODIFIED Requirements

### Requirement: the change-issue leg survives a label write the credential refuses (issue #775)

`registry_change_issue.set_labels` MUST treat a **refused** label write — the
`POST repos/<repo>/issues/<n>/labels` call exits non-zero naming `HTTP 403` or `not accessible
by personal access token` — as a recoverable event: print one loud `stderr` line naming the
issue and the reason, and return, so the change issue that was already filed stays filed and
the registry-sync job does not die on it. Every OTHER gh failure MUST still raise (a transport
or CLI fault is fatal). A write that exits 0 but is absent on the read-back (the #819 silent
drop) MUST still fail the step with `SystemExit` — an issue that exists but carries no queue
label routes the store review to nobody, and that stays a red step, never a quiet green.

[comment]: # (AC / how to verify: a fake gh whose label POST exits 1 with `HTTP 403` is filed
with the change issue created and the job green; a fake gh whose POST exits 0 but never stores
the label still reds the step naming issue + missing label. Existing green path unchanged.)

#### Scenario: the label write is refused by the credential

- **Given** a change-issue leg whose `gh api -X POST .../labels` exits 1 with
  `Resource not accessible by personal access token (HTTP 403)`
- **When** the change issue for a new store is opened
- **Then** the change issue is still filed, one `stderr` line names the issue and the 403
  reason, and the step returns successfully (does not raise, exit status stays 0)

#### Scenario: a write that claims success but dropped the label still reds

- **Given** a change-issue leg whose label POST exits 0 but whose read-back shows the label
  missing (the #724/#819 runner-PAT drop)
- **When** the change issue is opened
- **Then** the step fails loudly naming the issue and the missing label, via `SystemExit`

#### Scenario: any other gh failure is still fatal

- **Given** a `gh` call that fails for a reason other than a credential-refused label write
- **When** the change-issue step runs
- **Then** the failure propagates normally (a transport/CLI fault is not swallowed)

#### Scenario: the additive registry guard is untouched

- **Given** the current head which carries the merged #1981 store follow
- **When** `make sync-registry` and `make check-registry` run
- **Then** the store is unchanged (`generated_utc` `2026-11-04T15:29:04Z`, 117 models) and both
  gates are green; no registry content is edited by this change

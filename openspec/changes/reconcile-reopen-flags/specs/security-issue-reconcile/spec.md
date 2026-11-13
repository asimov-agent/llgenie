# Spec Delta: reconcile-reopen-flags

## MODIFIED Requirements

### Requirement: Scan-evidence reconcile shall reopen premature closes loudly

The scan-evidence reconcile leg SHALL reopen a closed-by-reference scan-evidence issue
whose finding is still reported by the latest scan, using a gh invocation that exists —
`gh issue reopen` — and SHALL abort loudly if the reopen fails. It SHALL NOT call
`gh issue edit` with a `--state` flag, which gh does not support.

#### Scenario: a still-reported finding reopens through the real subcommand

- **Given** a scan-evidence issue closed by a merged PR's bare `closes #N` while its
  finding is still in the latest scan reports
- **When** `make security-issues-reconcile` runs
- **Then** it issues `gh issue reopen <number>` followed by the explanatory comment, and
  issues no `gh issue edit` call carrying `--state`

#### Scenario: the crash point no longer truncates the batch

- **Given** a batch where an early issue needs reopening
- **When** reconcile processes the rest of the closed issues
- **Then** later genuine clears still receive their clearing comments (the batch survives
  the reopen)

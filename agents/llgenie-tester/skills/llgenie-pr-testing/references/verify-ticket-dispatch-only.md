## 12. ci(verify) dispatch-only tickets (the #1505 31-pipeline matrix)

These tickets have NO code PR — the vehicle is the dispatch itself (`auto=none (verification-only
vehicle: no PR exists to arm)`; the "persist a commit on tester/verify-<n>" rule does not apply).
Recipe: `references/verify-ticket-dispatch-only.md`. Key pitfalls:
- **A batch card covering many tickets can time out mid-procedure**; a sibling triage card for one of
  its tickets is fair game to finish, but post the claim comment on the ticket FIRST and check the
  umbrella ledger + the dead batch's claim comments for which dispatches already happened (#1482 @
  fc39b4180, run 43557277339).
- **A stale `gated: disabled_manually` ledger row is not current state** — `gh api
  .../actions/workflows` gives live `state`; #1879's restore re-enabled several. Read live state
  before honoring a gate.
- **Write full shas in posted evidence, never ellipses** — a truncated `fc39b4180...a376...` typed into
  a verify comment is a wrong sha, not an abbreviation.
- **A new issue created minutes after a green verify run is not that run's filing** — compare the run's
  job start/completion window against the issue's created_at and the issue's own subject.

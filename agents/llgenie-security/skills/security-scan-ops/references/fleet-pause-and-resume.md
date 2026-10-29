# When the fleet is paused (some or all workflows disabled)

Read the workflow states before treating a red run or a stuck PR as a defect:

```bash
gh api repos/asimov-agent/llgenie/actions/workflows --jq '.workflows[]|"\(.state)\t\(.name[0:60])"'
```

`disabled_manually` is a deliberate pause: file nothing against a paused workflow, and do not "fix" a
pipeline that is simply switched off. State it instead of idling silently.

- **A disabled workflow cannot be triggered and its runs cannot be re-run.** So "verify with a dispatch,
  then re-enable" is unbuildable: the order is `gh workflow enable <wf>` → verify (dispatch with
  `enforce=report`) → let the schedule take over. Re-enabling does not cancel runs already started, so a
  wrong verification dispatch is stopped by hand, not by flipping the switch back.
- **`CANCELLED` is not a verdict.** A cancelled check looks identical to a broken one on the PR page, so a
  held PR carries *"mergeable apart from a paused job"* — a different sentence from "BLOCKED". Re-run the
  cancelled jobs (`gh run rerun <id> --failed`) before anyone reads green as approval; that works while the
  workflow owning them is still active.
- Findings already filed go quiet: nothing clears a vulnerability issue except a scan run, so they stay open
  for the length of the pause and that is not a failure to fix.

## Resume order matters more than resume speed

```
merge the fix that clears the findings
  → gh workflow enable <scan workflow>
  → dispatch on main with enforce=report and require "0 finding(s)"
  → the next schedule closes the issues through the cleared path
  → re-enable the remaining workflows one family at a time
```

Land the fix before re-enabling the scan, or the first post-pause run re-reports advisories you already
explained and the board looks red for a reason everyone has to re-derive. Name which PR must merge first.

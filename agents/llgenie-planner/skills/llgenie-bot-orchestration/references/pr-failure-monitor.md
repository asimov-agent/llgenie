# Continuous PR/agent failure monitor (owner standing rule, 2026-10-30)

Owner directive: **monitor ALL llgenie agents and ALL open PRs; if a PR has FAILED, delegate it accordingly — this is always part of the main skill/behaviour.**

Every orchestration pass (and the tick) does a **real failure scan**:

```bash
# per open PR, read the checks at ITS HEAD (never an earlier sha)
h=$(gh pr view $n --json headRefOid --jq .headRefOid)
gh api repos/asimov-agent/llgenie/commits/$h/check-runs \
  --jq '[.check_runs[] | select(.conclusion=="FAILURE" or .conclusion=="CANCELLED" or .conclusion=="TIMED_OUT") | .name] | join(", ")'
```

- **Distinguish in_progress from FAILURE.** A scan that lists a running check as "red" invents work; `in_progress/-` is not a verdict. Only a *completed* FAILURE/CANCELLED/TIMED_OUT at the head is a red to delegate. cancelled is never green.
- **The planner's own gate workflows are not exempt.** The sweep extends beyond open-PR reds to main/default-branch workflow runs with NO PR attached — `CI`, `ci-verdict`, `ci-scope`, `engine-build` at `head_sha == origin/main` — because a red there is a main-red, not a PR-red, and has no open PR for `gh pr view` to surface. Query `gh api .../actions/runs` filtered by `conclusion == failure|cancelled` and by `head_sha == origin/main` on every pass, and triage each result like a PR red (attribute to an owner lane, delegate). A `ci-verdict`/`CI` red on main that only taunts a *different* run's head is a **cross-wired verdict check**, not a main-red: quote the real main-head verdict (`gh run view <legit-id>`) and trace the false two. Concretely: a `verdict: failure` at main that evaluates run `R` (whose guard is red on PR `#P`) is `#P`'s red cross-wired onto main's commit — main stays green, the PR `#P` red is the one to route.
- **A red at an open PR is a delegation trigger.** Read the failing job's logs (`gh api .../jobs/<id>/logs`), attribute the failure to an owning lane (shared-base / another lane's file / the PR's own product defect), and `message_agent` that lane with the PR id, the failing check name, the head sha, and what "fixed" means. One lane per PR; never two vehicles.
- **Never delegate a running job.** A fresh push re-runs CI; while `in_progress`, report it as "re-running", not as a failure to fix.
- Combine with the PR-count gate (references/pr-count-assignment-gate.md): the failure monitor runs on EVERY pass regardless of the <25 assignment threshold.

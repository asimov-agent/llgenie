# run-failure-reactor manual-dispatch verification — #1498

Durable record of the manual-dispatch proof that `.github/workflows/run-failure-reactor.yml`
behaves as intended (issue #1498, executed 2026-11-09; original evidence on #1498 comment
`6735895019`). The reactor is `workflow_dispatch`-only with a required `run_id` (issue #2293),
so the only way to exercise it is a manual dispatch — this is that proof, made durably reviewable.

## How to dispatch (the Actions-panel-equivalent)

```bash
gh workflow run run-failure-reactor.yml \
  --repo asimov-agent/llgenie \
  --ref <main-tip> \
  --field run_id=<id> \
  --field context=manual
```

`<main-tip>` is the `main` sha at dispatch time and `<id>` the completed run the reactor is asked
to route. `--ref <sha>` pins the workflow to a specific revision.

## Scenarios

| S | scenario | routed run_id | reactor run | head sha | verdict |
|---|---|---|---|---|---|
| S1 | not-fire (success) | `42586877266` | `42587824106` | `a5523974` | success |
| S2 | not-fire (cancelled) | `42586700722` | `42587885407` | `a5523974` | success |
| S3 | Route A → wake fix-bot | `42586989942` (PR#2373) | `42587961691` | `a5523974` | success, dispatch REFUSED HTTP 403 (finding) |
| S4 | Route B → deduped issue | `42582349730` | `42588102669` | `58874356` | success, filed issue #2378 |
| S5 | idempotent (re-dispatch) | `42582349730` | `42588200159` | `58874356` | success, no duplicate |

Run URL form used throughout: `https://github.com/asimov-agent/llgenie/actions/runs/<id>` (reactor runs: S1
https://github.com/asimov-agent/llgenie/actions/runs/42587824106 · S2
https://github.com/asimov-agent/llgenie/actions/runs/42587885407 · S3
https://github.com/asimov-agent/llgenie/actions/runs/42587961691 · S4
https://github.com/asimov-agent/llgenie/actions/runs/42588102669 · S5
https://github.com/asimov-agent/llgenie/actions/runs/42588200159).

## Checklist results

- **S1** — reactor `completed/success`, react job green; log `conclusion is "success" - not a
  failure, nothing to do`; no issue / no fix-bot / no claim.
- **S2** — reactor `completed/success`; log `was cancelled and a later run of "auto-merge" took
  over at 08:42:05Z - superseded, nothing to do`; no issue / no fix-bot dispatch.
- **S3 (Route A)** — reactor `completed/success`; claim comment on PR#2373
  (`<!-- bot-claim: run-failure-reactor … -->`); dispatch leg **attempted but REFUSED** by the API
  (`HTTP 403 — missing scope: workflow`); reactor handled the refusal exactly as designed — posted
  `bot-done: repair-unavailable` on PR#2373, released the claim, stayed green. **No new fix-bot run
  started** — see Finding.
- **S4 (Route B)** — reactor `completed/success`, react job green; log `-> llgenie-ci-pipelines-maintainer`
  and `filed: …/issues/2378`; issue **#2378** OPEN, createdAt after the run started, body carries
  the `run-fixer:` dedupe marker and the owning-lane label; exactly one issue for the class.
- **S5 (idempotent)** — reactor `completed/success`; log `already filed: <!-- run-fixer: … -->`;
  marker count unchanged (still `[2378]`); **no duplicate issue**.
- **S6 (never weakens / never merges)** — no tree change made by the proof; the reactor holds
  `permissions: actions: write, issues: write, pull-requests: write, contents: read` (no
  merge/push rights); Route-A artefact is a dispatch attempt (+ refusal comment), Route-B artefact
  is an issue file — never a merge.

## Finding and resolution

**Finding (S3):** the reactor's Route-A repair leg could not wake fix-bot end-to-end because the
dispatch credential it carried (`DISPATCH_TOKEN=secrets.BUMP_TOKEN`) lacked the API scope a
`workflow` dispatch needs (`workflow` on a classic PAT / `Actions: write` on a fine-grained one) —
`HTTP 403: Resource not accessible by personal access token`. The reactor **behaved correctly for
this refusal** (issue #2086): it stayed green, posted "repair unavailable" on the PR, and released
the claim so the branch was not left occupied. The failing checklist item — "a new fix-bot run
exists" — was an environment/credential cause, not a reactor defect.

**Resolved:** issue #2091 (CLOSED). The fix landed on `main` at `6f3d65b0` (per #412): the reactor
now dispatches the fix-bot with `github.token` (`GH_TOKEN`, `actions: write`) instead of the
`BUMP_TOKEN` PAT, and fix-bot's guard admits the repository bot on a `workflow_dispatch` (issue
#1571).

Everything else in the proof passed; the reactor's Route-A → guard/claim/dispatch code path ran and
acted correctly on the refusal, and Route-B + idempotency are fully green.

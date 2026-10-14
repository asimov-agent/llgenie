# The issue implementer never dispatched: two real-CLI bugs in the same call

## What was broken

`gh run list --workflow issue-bot.yml` showed **zero runs** for the implementer (its workflow merged
today, so the daily cron had not fired yet) — but a manual dispatch made it clear it could not have
worked either way. Three separate causes, in the order they bite:

1. **`gh` refuses `--comments` together with `--json`.** `scripts/issue_implementer.py::_thread`
   built `gh issue view <n> --comments --json number,title,body,state,author,labels,comments`.
   Real `gh` (2.102.0) exits 1: *"specify only one of --comments or --json"*. So `dispatch` died
   before it could pick an issue, on every run, and the workflow's report step then printed
   `invalid issue format: ""` because the action/issue outputs were never set. The refine path
   (#261) shipped in the same commit, so the refiner PR (#264) inherited the same call.
2. **The forced-issue check compared case-sensitively.** `dispatch` tested
   `detail.get("state") != "open"`, but `gh issue view --json state` returns the CLI's own enum —
   `OPEN` / `CLOSED`. With the argv fixed, the dispatcher then refused every real issue:
   `[issue-implementer] forced issue #260 is 'OPEN', not open`.
3. **The model key is not configured.** The workflow passes
   `NOUS_API_KEY: ${{ secrets.NOUS_PORTAL_API_TOKEN }}`, and that secret does not exist — the job
   env shows `NOUS_API_KEY:` empty, so `make hermes-smoke` stops at its own guard:
   `NOUS_API_KEY unset - refusing to spend time on a dead key`. That is a repo-secret action, not a
   code fix, and it is the only remaining blocker on the implementer path.

## Why the tests were green while the product was broken

Both bugs lived in the **argv and the enum**, and the suites answer them with a fake `gh` on PATH:
the fake happily accepted `--comments --json` and its fixtures used lowercase `"open"`, so the code
agreed with its own fixture instead of with the CLI. A stand-in must encode the CLI's *constraints*
and its *real values*, not just its happy answers.

## What changed

- `_thread` asks for the comments through `--json` alone.
- The state check is case-insensitive, and the fixtures now carry the real `OPEN` / `CLOSED`.
- New regression test `test_no_gh_call_combines_comments_with_json`: it runs a full dispatch and
  scans **every** argv the product built for the combination the CLI rejects.
- `openspec/changes/issue-bot-triage/spec.md` no longer prescribes the broken flag (`--comments`
  plus `--json` is spelled out as refused) and carries `**Test:**` references for the two scenarios;
  `tasks.md` records the fix.
- The same one-line argv fix went into the refiner's branch (PR #264, `scripts/issue_refiner.py`),
  which had copied the call.

## Verified against the live repo (no mocks)

```
$ make issue-bot-dispatch REPO=asimov-agent/llgenie FORCE_ISSUE=260 DRY=1
[issue-implementer] picked #260: docs: README still describes the old CI trigger model ... -> agent/issue-260-docs-...
action=dispatch
issue=260
branch=agent/issue-260-docs-readme-still-describes-the-old-ci-t (daily count 0/3)

$ make issue-bot-dispatch REPO=asimov-agent/llgenie FORCE_ISSUE=261 DRY=1
[issue-implementer] forced issue #261 is 'CLOSED', not open
action=none

$ python3 scripts/issue_refiner.py pick --repo asimov-agent/llgenie --dry
[issue-refiner] picked #91: Flag audit: ... (body + 1 comment(s)); refine-in.md written
```

The dispatch and the refiner's pick both work against the real `gh` now. What remains before an
end-to-end implementer run can go green is the missing `NOUS_PORTAL_API_TOKEN` repo secret.

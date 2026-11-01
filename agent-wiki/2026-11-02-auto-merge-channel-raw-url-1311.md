# 2026-11-02 auto-merge channel query uses the raw URL-string form (issue #1311)

`scripts/auto_merge_channel.py::ci_run_count` answered "which engine merges a head" with
`gh api -f head_sha=… -f event=… -f path=…` — the form-encoding `gh` 2.103.x rejects on
`GET /repos/{owner}/{repo}/actions/runs` with a spurious 404 on **every** head, so the
`auto-merge` sweep (run `41304690971` at `eefaac21`, failed 12:04Z) read a refusal as
"no CI run" and could not route a green open PR head (`channel=ci`) at all; it flapped red
while the CI completion was the correct merge owner.

The query now uses the repo's own raw URL-string convention (`resolve_run_pr.py:101`,
`ci_requeue.py:72`):
`gh api "repos/{repo}/actions/runs?head_sha=…&event=pull_request&path=.github/workflows/ci.yml&per_page=1" --jq .total_count`
— the exact invocation the API accepted (200, `total_count=3` on an open code head).
The change is scoped to the channel query mechanism only: it does not change which workflow
merges what, and the **404-is-a-LOUD-failure** doctrine for a genuinely unconfirmable head is
unchanged.

Two hardening pieces with tests:

- **Bounded transient retry** (`_gh_retry`, mirroring `architecture_bot.py`'s `TRANSIENT`):
  a 502/503/504 gateway or a timeout (the answer LOST, not a verdict) is retried up to 3
  times with a 1 s backoff before the loud failure. `tests/test_auto_merge.py`:
  `test_a_transient_gateway_error_is_retried_and_recovers` — two 502s then "1" ⇒ `ci_run_count == 1`.
- **A real 404 stays loud on the FIRST attempt** — never retried into a silent
  `channel=auto-merge`. `test_a_genuine_404_is_loud_on_the_first_attempt` pins one call then
  `RuntimeError`, and `test_a_docs_only_head…` now asserts the argv carries the params IN the URL
  with `"-f" not in call`, so the `-f` form would red the suite.

`linux/unit`, `linux/install`, `guard` must pass on the PR (owner-gated #1088; never merged here).

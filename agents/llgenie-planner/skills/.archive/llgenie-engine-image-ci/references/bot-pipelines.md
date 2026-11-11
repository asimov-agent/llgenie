# Debugging llgenie's bots (rebase / issue / fix) when they “do nothing”

A bot run that ends green while changing nothing is the normal failure mode here. Diagnose in this
order — each step below produced a real “the bot never worked” bug.

## 1. Read the decision output before the prose

`gh run view <id> --log | grep -E '\[rebase-bot\]|action=|pushed|==> rebasing'` (same shape for
`[issue-bot]`). The decision prints its verdict plus a reason for every item it passed over. That
list is the bug report; do not start from the summary or the job conclusion.

## 2. Never decide from an uncomputed value

GitHub computes a PR's mergeability lazily: `mergeStateStatus` is `UNKNOWN` right after a push or a
comment — often for **every** PR in that listing. A sweep that treats `UNKNOWN` as “needs nothing”
skips exactly the PRs that need work, forever, because each 6-hourly run sees it again.

- Re-ask the single item: `gh pr view <n> --repo <r> --json mergeStateStatus`, bounded
  (`UNKNOWN_ATTEMPTS`, `UNKNOWN_DELAY_S`), then use the resolved value.
- A value that never resolves is *deferred* and named in the pass-over list — never filed under
  “does not need work”.

## 3. “Already done today” must read the DONE marker, not any comment

A regex like `rebase-bot.*<date>` over the whole thread matches the bot's own **claim**
(`<!-- bot-claim: rebase-bot … -->`), and the workflow's own PR body. Result: one failed attempt
marks the item done for the rest of the UTC day.

- Count only the authoritative release: parse `bot_claims.DONE_RE` and require bot + kind
  (`rebased`); never a claim.
- The actor writes a **distinct kind** on failure (`gave-up`), so a failed attempt does not consume
  the day. One comment helper taking a `kind` argument beats a hardcoded `"rebased"`.
- Eligibility is the CURRENT state, not history: a PR rebased this morning and re-dirtied by a
  later merge must be rebased again today. Markers bound the daily CAP only.

## 4. A failure must leave a clean tree

A conflict can be **in `Makefile`** (bot PRs edit it constantly). If the actor exits with the rebase
still stopped, the next `make` in the same run dies with `Makefile:N: *** missing separator` and the
rest of the run is lost. Call `git rebase --abort` (a no-op when nothing is in progress) on every
failure path.

## 5. Bootstrap circularity: `make` cannot parse a conflicted Makefile

Any nested `make` invocation dies when the file it must parse is the conflict:

- Snapshot the Makefile **before** the checkout and invoke through it:
  `MK=$(mktemp); cp Makefile "$MK"; … make -f "$MK" <agent-target>`.
- The container side must NOT run `make` again: run
  `hermes -z "$(cat)" $(nous-alias) --reasoning medium --yolo` directly inside the image. Keep
  `$(nous-alias)` on that recipe line — `tests/test_issue_implementer.py` requires every
  `hermes -z` line to derive the model from that one pin.

## 6. One item per run starves a backlog — loop, bounded, with a skip list

A scheduled bot that handles ONE PR per run loses a race against `main` moving. Loop the decision in
the workflow: re-ask the sweep after each success, stop when it answers `none`/`cap`, bound with a
`max_prs` dispatch input.

- Pass the handled numbers back in (sweep `skip` / CLI `--skip`), or the same PR is picked again in
  the same run.
- Add a PR to `skip` on **failure too**: a failed rebase leaves it stale, so without this the loop
  retries the same conflict up to the bound, each attempt a model call.
- Default the bound **inside the step** (`MAX_PR="${MAX_PR:-10}"`): `tests/test_bot_decision_loudness.py`
  runs each decision step alone with a crashing `make`, and a bound that comes only from the job's
  `env:` means the loop body never runs — the step then exits 0 on a crashed decision.

## 7. A merged fix is not a landed fix

The agent's branch can keep commits pushed **after** the squash merge. Confirm on the base, not the
branch:

```bash
git fetch origin main --quiet
git show origin/main:<path> | grep -c <the_symbol_you_added>   # 0 => main does not have it
```

Filter by symbol, never by commit sha (a squash merge rewrites it). If it is 0, file the remainder
as its own issue + PR instead of amending the merged change.

## 8. Test fixtures must encode the artifact's real shape

A fixture that mirrors the parser's buggy pattern (e.g. `<!-- rebase-bot: <date> -->`) hides the bug
while the test stays green. Write markers exactly as the producer writes them
(`bot_claims.claim_comment` / `done_comment`) and assert both directions: the claim does NOT count,
the done marker DOES.

## 9. Small harness facts that cost a run

- `gh pr view --json merged` is not a field; use `state` / `mergedAt`.
- `gh pr checks` can print “no checks reported” while runs exist for a fork PR — use
  `gh run list --repo <r> --branch <b>`.
- `gh pr list --json mergeable,mergeStateStatus` is the cheap way to see what the bot sees.
- A dispatch runs the **default branch's** workflow file, so a fix on a feature branch cannot be
  exercised by dispatching it: merge first, then dispatch.
- Live evidence beats a claim: call the fixed decision function read-only against the real repo
  (`python3 -c 'import …; print(fn(...))'`) and record the printed verdict in the PR body.

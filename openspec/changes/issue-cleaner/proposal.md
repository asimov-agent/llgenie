# issue-cleaner — proposal

Issue: [#325](https://github.com/asimov-agent/llgenie/issues/325)

## Why

`make check-pr-hygiene` reads the producers the repository owns (workflows, Makefile, `scripts/**`), so it
catches a commit or PR *body* that is empty or a placeholder. It cannot see what happened at PR time:
whether the PR that merged actually **closed** the issue it implements.

GitHub closes an issue at merge only when the body carries a closing keyword bound to it. When it does not,
the PR merges and the issue stays OPEN — the tracker then says "not done" about work that shipped. Measured
on `main`: 13 of 38 merged PRs carried no closing reference, and this bot's first real catch was **#256**,
implemented by merged PR **#344** (`closingIssuesReferences: []`, merge commit `6601051` opening with
`Issue: #256`) and left open by it.

Nothing in the fleet covers this. #325 names the reporting half; the closest siblings are #293 (the
reviewer files a finding an open PR already fixes) and #279 (the shared claim protocol) — neither reads a
merged PR's linkage.

## What changes

- `scripts/issue_cleaner.py` — read the recently merged PRs and the open issues and decide, per merged PR,
  the issue it implemented, from three signals in strength order: `closingIssuesReferences` (non-empty means
  it closed its issue — nothing to do), the **merge commit**'s `Issue: #<n>` line, then the **title**'s
  trailing `(#<n>)`.
- **The remainder rule is the correctness of the bot.** A signal that resolves to a still-open issue is a
  candidate UNLESS the PR's own body lists that issue under `Not covered`. A remainder is a first-class
  linked work item per AGENTS.md, not a missed close. #344 named #339-#343 under `Not covered` while
  implementing #256, so #256 is a close and #339-#343 are remainders — a bot that could not tell them apart
  would close work still being tracked.
- `make issue-cleaner-scan` prints every finding with its evidence and closes nothing;
  `make issue-cleaner-apply` posts the evidence comment and closes. `scripts/bot_claims.py` gains the
  `clean` verb so the bot announces itself on the issue before mutating it (#279).
- The scan stays OUT of the offline `ci-unit` path: it needs the API. Its tests stub `gh` on `PATH` and are
  hermetic, so `tests/test_issue_cleaner.py` runs in `make test-unit`.

## Not covered

- **Closing the product-code half of #256**: `scripts/hf_auth.py` `hub_open` still re-raises on the first Hub
  5xx. That is **#339**, product code and its own reviewed change.
- **The reporting workflow** (a scheduled job that surfaces the findings): #325 asks for the check where the
  API is available. The decision plus the two make targets land here; wiring a schedule is its own change
  and is tracked by #325's own remaining scope.
- Branch protection / approvals: a GitHub-side control, not a repo file.

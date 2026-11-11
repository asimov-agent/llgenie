# Canonical issue-body gate (rule 37): six sections, checkbox criteria, no extra headings

**Trigger:** you are about to file, restate, or refine any llgenie issue body, and it must pass `scripts/issue_body.py` (the front-door gate every `agent:implement` issue is checked against). A body that fails `issue_body.missing()` is unroutable — the queue silently drops it.

## The canonical shape (order matters, `## Technical` LAST)

1. `## Problem`
2. `## Why it matters`
3. `## How we fix it`  (this is where an old `## Proposal` belongs)
4. `## Benefit`
5. `## Acceptance criteria`
6. `## Technical`

`issue_body.missing()` returns the missing ones; `NONE`/empty = gate-clean.

## The three non-obvious failure modes

- **Extra `##` headings are REJECTED as `unknown section(s)`.** Only the canonical six (plus an allowed `## Not covered`) are accepted. A body that adds `## Evidence`, `## Ownership`, `## Related`, or `## The N tickets` as their own `##` headings fails the whole gate even though all six canonical sections are present. Fold every supplementary block (evidence, ownership, ledgers, related refs) UNDER `## Technical` as bold label paragraphs (`**Ledger — …:**`, `**Related:**`), not as `##` headings.
- **Acceptance criteria must be `- [ ]` checkbox rows, never a numbered `1. 2. 3.` list.** A numbered list fails as "`## Acceptance criteria` is missing" (the gate looks for checkbox items). Convert every acceptance item to a `- [ ]` row.
- **Non-canonical source headings need mapping, not deletion.** An issue filed with `## Problem / ## Proposal / ## Acceptance / ## Ownership / ## Related` maps cleanly: Proposal→How we fix it, Acceptance→Acceptance criteria (as `- [ ]` rows), and Why it matters / Benefit / Technical derived from the existing Problem/Ownership/Related prose. Preserve every fact; restate the structure only.

## Verify before and after

```bash
# local file
python3 -c "import sys;sys.path.insert(0,'scripts');import issue_body;print(issue_body.missing(open('<body>.md').read()) or 'NONE — gate-clean')"
# live wire (read back after gh issue edit)
gh issue view <n> --repo <o>/<r> --json body --jq '.body' > /tmp/rb.md \
  && python3 -c "import sys;sys.path.insert(0,'scripts');import issue_body;print(issue_body.missing(open('/tmp/rb.md').read()) or 'NONE — gate-clean')"
```

Also assert the section order (`## Technical` last) and that acceptance items are `- [ ]`.

## Ticked criteria on an OPEN issue

Distinguish two cases before un-ticking: **fabricated pre-ticks** on an in-progress issue with no evidence behind them → un-tick to `- [ ]` (the gate wants outcome rows). But a `- [x]` row that an honest ledger/verify-comment backs (verify ticket family, per-ticket `verify` comments) is real state — preserve it. When unsure, measure the evidence (per-issue `verify` comments) first; un-ticking an honest ledger destroys real state.

# Fix: the pairwise dedupe bots scan every open issue, paged to exhaustion, not one newest-first page of 200

## Why

`scripts/issue_dedup.py` (`candidates`) and `scripts/issue_cleaner.py` (`open_issues`) both scan the open
board with `gh issue list --state open --limit 200` — a single newest-first page capped at 200. As a
board grows past 200 open issues, the OLDER half of the board — exactly where the originals of a
duplicate/stale pair live — becomes invisible to the pairwise sweep. Measured: `registry_change_issue`
sat at open-list position 110 behind a 100-window filer and was missed (#2659, filed against #2847).
The same class of blindness hits these bots the moment the open board passes 200.

## What changes

1. A shared paginated scan, `bot_claims.paginate_open_issues`, walks the GitHub API
   `repos/{owner}/{repo}/issues?state=open&per_page=100&page=N` until a SHORT page (< 100), filters
   out pull requests (the `issues` endpoint returns them too), and normalises keys to the shape
   `gh issue list --json` produced (`createdAt`). No fixed window; the whole board is read.
2. `issue_dedup.candidates` and `issue_cleaner.open_issues` route their open scan through that helper
   (each via its own `gh` transport seam). Pairwise duplicate and stale-open coverage now extends to
   the entire open board regardless of size.

## Who

llgenie-issue-bot-maintainer (both scripts are issue-bot legs). The parent `registry_change_issue`
scan fix is its own change (#2848).

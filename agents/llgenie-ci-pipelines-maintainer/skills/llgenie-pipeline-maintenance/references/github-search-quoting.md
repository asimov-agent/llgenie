# GitHub issue-search quoting (issue #1990)

`gh issue list --search '"<marker>" in:body'` cannot express a double-quote inside the quoted
phrase. When a marker embeds a workflow display name that contains a `"` — `ci-verdict — … and
says "no verdict" out loud` — the phrase is broken by the interior quote, returns 0 every time,
and a duplicate issue is filed per failing run (13 issues for one head+job+step). GitHub's index
treats `"` as a separator, so the quote-stripped phrase still finds the marker exactly as written
in the body.

Fix pattern (applied in `scripts/run_failure_reactor.py`): strip `"` from the marker before
building the `--search` phrase (`marker.replace('"', '')`). Prove it live (exact marker → 0,
stripped → N) and with a gh stub that models the nested-quote rule (a query with an interior quote
matches nothing; only a quote-free phrase reaches the marker match).

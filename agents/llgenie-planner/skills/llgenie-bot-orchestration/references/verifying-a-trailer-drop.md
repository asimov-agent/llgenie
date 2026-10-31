# Verifying a co-author trailer is gone (don't trust a bare grep)

`check_pr_authors.py` fails a PR when any commit in `base..head` carries a `Co-authored-by:` trailer whose name/email is outside the allowlist. Removing those trailers requires a history rewrite, so knowing whether it actually worked matters.

**A bare `grep -c '<address>'` on `git log --format=%b` is NOT a valid check.** A commit that *documents* the trailer rule contains the address in prose and will match:

```
761fcd5  line 4: ("architect@llgenie.local" -> {"LLGenie Architect"}, because Co-authored-by trailers in …
e65708e  line 7: <architect@llgenie.local> on two stacked-PR squashes) added as its own paragraph.
```

Neither is a trailer; both are sentences about trailers. A bare grep sent a lane back to re-run `filter-branch` on an already-clean branch.

## The two checks that are valid

1. **The gate itself**, which parses trailers with a line-anchored regex:
   ```
   make check-pr-authors PR_BASE=<main-sha>      # exit 0 == no violations
   ```
2. **A line-anchored grep**, if the gate is unavailable:
   ```
   git log --format=%b <base>..HEAD | grep -E '^[[:space:]]*Co-authored-by:.*<address>'
   ```

The anchor matters: `check_pr_authors.py`'s own `COAUTHOR` regex is `^[ \\t]*co-authored-by:` with `re.MULTILINE`, so a trailer is a *line*, and prose mid-sentence is not.

## Rule

Before instructing a history rewrite, run the gate (or the anchored grep). Reporting "the trailer is still there" from an unanchored match costs a full CI cycle and risks a needless `filter-branch` over a stack root that other PRs are based on.

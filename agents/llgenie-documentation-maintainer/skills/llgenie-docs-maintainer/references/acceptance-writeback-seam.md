# Acceptance write-back: run the seam, never tick by hand

Closing the "acceptance criteria not ticked" gap on an issue means running the sanctioned
write-back script. Never hand-edit the checkboxes — the seam adds the `proven:` provenance a
reviewer reads.

## Procedure

1. Save and inspect the body: `gh issue view <n> --repo <o/r> --json body --jq .body`. Count the
   boxes (`grep -c '^- \[ \]'`) and confirm the section heading text.
2. **Canonicalize the heading first.** The seam locates the section with an EXACT match — the
   equivalent of `m.group(1).strip() == "Acceptance criteria"`. A hand-authored heading carrying a
   suffix, e.g. `## Acceptance criteria (what closing means)`, silently defeats it: the seam finds
   nothing and refuses. Fix with a single-line `gh issue edit <n> --body-file` that changes only
   that one line to `## Acceptance criteria`; then re-count and confirm no box or other heading
   moved. Never reflow the rest of the body in the same edit.
3. The write-back script (`acceptance_writeback.py`) is NOT in a dirty working checkout's
   `scripts/`. It lives on `origin/main`. Extract it and every sibling module it imports from
   `origin/main` into a scratch dir, then run with `PYTHONPATH` pointing at that dir or the
   checkout's stale `scripts/` will shadow the modules and the run fails on import:
   `PYTHONPATH=<scratch> python3 <scratch>/acceptance_writeback.py writeback --issue <n> --repo <o/r> --proven 1,2,3,... --verdict-ref '<ref>'`
4. `PATCHED #<n>` + rc=0 means the body was updated. **Read back**: `proven:` count == box count,
   `- [x]` count == box count, `- [ ]` == 0, and the `updatedAt` moved.

## Pitfalls

- **The tick does not reopen or close the issue.** Ticking a CLOSED issue leaves `closedAt`
   untouched — that is correct, not a failure.
- **Re-run idempotently at the live main tip.** The seam is idempotent. If `origin/main` advanced
   after your first run, re-run it at the new tip so the `verdict-ref` names the sha a reviewer will
   actually read. Always `git fetch` + `git rev-parse origin/main` before quoting any sha.
- **Never write-mode sync another lane's live dir** to make a doc "tick" — live is the source of
   truth; a write-mode sync truncates a richer live silently.
- **Reading comments:** use the list endpoint, `gh issue view <n> --json comments`. A per-comment
   path (`GET /issues/<n>/comments/<id>`) 404s — the comment exists but is only reachable through
   the list.
- **A progress guard that keeps claiming "no task-relevant mutation" after the wire already moved**
   is not answered by fabricating a mutation. Re-measure the wire; if `origin/main` has advanced
   since your run, the idempotent re-run at the new tip is the genuinely owed mutation — it is both
   the correction and the proof.

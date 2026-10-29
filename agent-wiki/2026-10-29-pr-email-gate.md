# The author gate matches the commit email, not the display name (#840)

> Measured against `upstream/main` **98466eb** (the sha #993 was fetched from), verified at head `b99c028`.

GitHub's squash of a PR commit writes the author's **display name from the account profile**, not from the
committer — so on this repository a squash lands as `Andy <andy.holst@protonmail.com>` while the branch's own
commits read `Andy Holst <andy.holst@protonmail.com>`. The email is correct in both; the name is GitHub's
rewriting of the profile.

A name-match author gate therefore reds every squash: `Andy`, `andyholst` and `Mr. Asimov` all fail the
exact-spelling check even though they are the same two people at the two allowed addresses. The wrong fix was
rewriting history to satisfy a field the committer cannot set — it would have made every future squash a
re-author.

- `check-pr-authors` now keys on the EMAIL (`email in ALLOWED.values()`), and the display name is informational.
- A foreign ADDRESS is still a violation whatever the name says (`Andy Holst <someone@else.example>`).
- The repository's own **producers** are still held to the name-and-address pair, because a workflow author
  types `user.name` by hand and can control it — only GitHub's merge machinery is freed of the name.
- The docs of record (`AGENTS.md`, `docs/BOTS.md` §author, the `make check-pr-authors` help, the script
  docstring) were updated to say "the address is the gate", so doc and measurement agree.
- Dated history (the `2026-10-16` change record, the #345 wiki note, the openspec proposal) is left as the
  record of when the rule was name-matched.

Verified at `b99c028`: `pytest test_pr_authors.py + test_git_identity.py` → **38 passed**; negative control
(name-match planted back) → the squash tests red, restored → 38 passed; `check_pr_authors.py check` → OK;
`check-workflows/check-wiring/check-docs/check-pr-hygiene/lint` → exit 0.

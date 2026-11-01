# docs: document `check-pr-closing` / `pr-closing-report` in the docs surface (#1336)

`#1334`/`#1329` merged two user-facing make targets, `check-pr-closing` and
`pr-closing-report`, each carrying a `##` help line — the user-facing surface
`make help` prints — but documented them only in `AGENTS.md` and change-note
fragments, not in the documentation surface (`README.md` + the `docs/` files
the README links). `make check-docs` matches every user-facing target
whole-token against that surface and reds on a target that is both
user-facing and unnamed anywhere in it.

Docs-only fix (issue #1336, documentation-maintainer owned): the two targets
are automation targets, so they belong in `docs/BOTS.md` with the other PR
guard-family rows (`check-pr-hygiene`, `pr-hygiene-report`, `check-pr-authors`,
…), one line each mirroring the Makefile's `##` help text. No Makefile logic,
no script, no workflow change — the targets' behaviour is already on `main`
and green; this closes only the docs-surface gap so the gate stops redding on
every branch living at a base that predates `#1334`'s merge.

Verified before the fix: `make -s check-docs` red on a clean `origin/main`
worktree with exactly the two problems named (`check-pr-closing` and
`pr-closing-report` user-facing but documented in neither `README.md` nor
`docs/`). After the fix the gate reads the two targets in `docs/BOTS.md` and
passes rc 0 at the head.

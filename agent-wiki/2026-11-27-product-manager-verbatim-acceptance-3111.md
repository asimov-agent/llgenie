# Product manager: carry acceptance wording verbatim (issue #3111)

PR on branch `agents/3111-pm-skill-ac-fidelity`, cut from freshly fetched
`origin/main@4b1fcb2bbee47b57d697b96e8737089a00cde952`.

## What changed

- `agents/llgenie-product-manager/skills/llgenie-product-manager/SKILL.md` now carries the
  acceptance-fidelity pitfall that was live-only on the host: carry the analyst's/planner's
  acceptance wording VERBATIM into the criteria you write; do not paraphrase a verification
  surface into a different one. Concretely, a framed AC that says the gates must pass
  "on the merged tree" is NOT the same as "at the PR's final head" — name both when both
  are required and cite the merged sha. The lesson came from #3087, where an AC1 wording
  drift ("PR final head" vs the analyst's "merged tree") cost a corrective comment and left
  two records to reconcile.
- The tree file is byte-identical to the live profile copy: 13200 b, sha snapshot
  `e5b421ed0e19` (the exact live snapshot named in the #3111 audit table). Every other line,
  including the #2145 `$HOME` rule, is unchanged.

## Why it is versioned

A local edit to the live profile copy at
`$HOME/.hermes/profiles/llgenie-product-manager/skills/llgenie-product-manager/SKILL.md`
fixed the behaviour on-host but left the tree stale, so the next profile sync would have
erased it (#791 / #928). The docs lane's audit at `origin/main` `4b1fcb2bbee47b57d69`
(#3111) measured the drift (`live-longer` + `live-edited-not-tree`, 12725 b tree vs 13200 b
live) and routed this one file back to its owning lane. The exact paragraph now lives in
the repository; the owner runs
`make sync-agent-profile PROFILE=llgenie-product-manager` after this PR lands. This lane
does not edit the live profile during the sync.

## Key decisions

- Tree is canonical (`agents/README.md`); direction is tree ← live for the one reviewed
  paragraph only — no live bytes folded wholesale, no other lane's file touched (the
  architect and pr-reviever rows of #3111 are owned by those lanes).
- No `/home/<user>` literal (#2145) — the file uses `$HOME` in shell/doc contexts.
- The note and one-row `docs/changes.d` fragment are the #1123 companions for the
  behavioural change; `CHANGES.md` is rendered with `make changes-index`.
- No claim on the #3111 umbrella: this is one of three lane PRs and the issue stays open
  until all three land, so the subject and title do not carry a `(#3111)` closing claim
  (#3111 is named in prose here and in the PR body only).
- No self-tick (#1644), no hand-merge (#1088), no arm, no second vehicle.

# tester lane live→tree fold, round 8 (2026-11-01) — issue #1079

Versioning the tester lane's live→tree drift at `e37513ba` (#1310's merge — the fold that versioned
`fold-live-profile.py`). Live accreted two lessons that #1310's OWN execution proved. Byte-copied
live→tree with the (now-versioned) tool itself: `scripts/fold-live-profile.py --profile llgenie-tester
--copy` — 5 files same, 2 copied OK, 0 live-missing, 0 mid-write; both destination hashes re-read to
match live.

## Lesson 1 — a fold is a SEQUENTIAL dependency chain, never a batch (#1079, proof: #1310)

edit → gate → commit/amend → push → open/create is a strict order: each step consumes the previous
step's output, so fanning several of them into one parallel tool-call batch runs them CONCURRENTLY on
a half-built tree. #1310's own execution hit exactly this: the wiki-note fix, the amend, the push and
the PR-create were all issued in one batch because they had looked independent — the note still lacked
its `#<n>`, so `check_docs` redlined, the commit carried the broken note, and the create fired on the
wrong head. The batch must be one mutating call at a time, reads may be batched, and the gate must go
green BEFORE the amend+commit, not after.

## Lesson 2 — `check_docs.py` requires every wiki note to name a literal `#<n>`

`agent-wiki/` notes must reference an issue or PR as `#<n>` — a note describing the work in prose but
never writing `(#1234)` reds `references no issue or PR (\`#<n>\`)`. Put the id in the note's own
heading or body; the check is a text match on the backtick-quoted form, so a bare `1234` does not
satisfy it. Two traps around that red: an edit that reassembles the file from `splitlines()` drops the
trailing newline and reintroduces `lint_linefeeds` — and because the gate reads COMMITTED paths, the
fix must be staged and amended before `check_docs` can go green. Run
`changes_index.py check && check_docs.py check && check_architecture_census.py check &&
lint_linefeeds.py` as ONE chain and only then amend.

Also folded verbatim: `check_docs`/`check_architecture_census`/`changes_index` chain is the docs gate;
`check_agent_profiles` is a SEPARATE target (the fleet-wide live-drift red is not part of `check-docs`).

## Proof at the committed head

`SKILL.md` `a0707de620d3 == live`; `agent-profile-versioning.md` `0d3249b1e862 == live`; 5 other lane
files byte-identical (SOUL + 4 references) per the tool's own table; `make changes-index` + the four-gate
chain green at HEAD.

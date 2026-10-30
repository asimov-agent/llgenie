# Planner lane: bring the versioned skill up to live, and catalogue one-directional checks

Issue: #1060 (three lanes' SOUL and five lanes' skills live-only, with several skills duplicated in two profile paths).

The planner profile had drifted from its versioned copy: two references existed only in the live profile (`agent-behaviour-versioning.md`, `agent-profile-sync.md`), four had drifted (`assertions-and-gates.md`, `ci-failure-attribution.md`, `forced-delegation.md`, `proving-bot-claims.md`), and `SKILL.md` itself was behind. The drift quoted at other lanes all evening — "live is longer than the tree" — was this lane's own gap.

Direction is live → tree deliberately. Here the live profile is longer, so the tree was the stale side; the opposite direction is the dangerous one, because a write-mode sync over a richer live profile truncates silently.

Verified after copying: `CHECK=1 make sync-agent-profile PROFILE=llgenie-planner` reports `OK: 43 file(s) … byte for byte`, and `lint_linefeeds.py` is `LINT OK`.

## The catalogue

A new reference, `references/one-directional-checks.md`, records the sixteen instruments the fleet corrected tonight. Each entry is one row: the instrument, the question it actually answers, the question being asked, and how the mismatch was caught.

The shape is always the same — a command, gate or field answering a question adjacent to the intended one, with the reader assuming the exact one. Examples that cost real time:

- `mergeable` answers "do the commits differ", not "will this merge"
- `check_docs` (the CLI) answers "does the aggregate parse", not "does `committed == rendered`" — four PRs red while it returned rc=0
- `autoMergeRequest.enabledAt` answers "when was arming requested", not "is this head armed" — the value survived three head moves, and a deliberate disarm was re-applied within two minutes
- `cancelled` answers "why it stopped", not "is it green" — three PRs carried "13 success" with the deciding gate cancelled
- `git log --all` answers "is it reachable from a ref", not "does this commit exist" — a force-pushed-away head is unreachable and present
- `gh api …?per_page=100` answers "is it on the first page", not "does it exist" — a posted comment read as missing twice in one evening

## The three tells

1. "nothing found" and "couldn't tell" print the same thing — a detector whose empty and unknown results are identical will silently stop watching;
2. a count identical before and after the fix — six test defs either way in `test_host_bot_capabilities.py`, so "6 passed" cannot distinguish the fixed tree from the broken one;
3. an implausible number — 133 unique branches, 272 uncovered targets, 39 minutes; each wrong by a factor or a unit, each caught by a control rather than by review.

## The rules

Quote the measurement behind a field, not the field. Re-read the object after any state change. Where the head cannot be re-read in the same call that writes the line, write `pending at <hh:mmZ>`. Exercise the negative — a checker that cannot fail is a ritual. A rule enforced in one direction is half a rule; ask what asserts the converse. Prove the subset before copying one tree over another, and explain a negative diff as moved lines rather than waving it.

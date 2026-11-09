# Per-lane acceptance contracts live in the tree — grep under agents/, never declare absence from a subset or an assumption

## Rule

When a verdict-gated AC requires "each affected lane carries, via #791, a stated form contract under
`agents/<lane>/`" (e.g. #1796 AC1), do NOT declare that text "absent from the tree" off a first grep that
matched nothing in a narrower scope, and do NOT assume a PR that ships zero `agents/` files also fails the
"each lane carries it" criterion. The per-lane contract text usually ALREADY lives under `agents/` on main
from separate merged lane-versioning PRs, and the gate PR under review may simply be the PR-body GATE that
closes the umbrella issue.

Measured (reviewer error, corrected on-wire 2026-11-06, #1804/#1796): verdict 5807673214 claimed "no
per-lane contract text locatable under agents/" after a (targeted) grep; the truth is the verbatim
contract ("Every issue this lane files AND every PR body it opens carries a `## Acceptance criteria`
section ... text-only under `agents/<lane>/`, versioned via #791 ... SYNC per #1724") is present at the
reviewed head in `agents/llgenie-status-keeper/.../SKILL.md`, `agents/llgenie-pr-merge-conflict/.../SKILL.md`,
and `agents/llgenie-planner/.../acceptance-form-rule.md` — landed by MERGED lane PRs (#1798, #1813, #1814).
The AC was held ONLY because the implementer-lane contract was still OPEN (#1817), not because the contract
text was absent. Retraction discipline applies: name the false claim, post the correction on the PR/its
issue thread (quote the sha + the measurement), withdraw rather than soften.

## How to measure it properly

- Run the grep across the WHOLE `agents/` dir for several contract idioms, not one wrapper phrase:
  `grep -rln "every PR body it opens" agents/`, `grep -rln "form contract" agents/`,
  `grep -rln "## Acceptance criteria" agents/` and `grep -rln "#1724" agents/`. A single phrase grep on
  `agents/*` can return 0 while the text genuinely exists.
- When the criterion is "each AFFECTED lane carries ...", enumerate WHICH lanes are affected and require
  the text under EACH lane dir; a partially-satisfied fleet (3 lanes merged, 1 open PR) means the criterion
  is "meaningfully met but not fleet-complete" — set the exact re-judge condition (when the open PR merges,
  tick) instead of declaring it absent or fully proven.
- Check whether the per-lane PRs are already merged on main (`gh pr list --state all --search` or
  `git log` for the lane dir), because the gate PR under review may not be their vehicle.

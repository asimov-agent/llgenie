# Universal acceptance-criteria form rule (owner directive 2026-11-05)

**Rule (fleet-wide, versioned per-lane via #791; carriers #1796/#1792):** every issue AND every PR a fleet lane files carries a `## Acceptance criteria` section whose items are each a `- [ ] ` markdown checkbox — one per provable outcome. A criterion a reviewer cannot tick is not one (#745). The CI validates it for BOTH issue body content and PR body content.

## Current enforcement map on origin/main (measured 0d003157)

| Population | Enforced? | Where |
|---|---|---|
| Producer-rendered issue | YES | `scripts/issue_body.py` six sections, `## Acceptance criteria` with >=1 `- [ ]` (#745); `make check-issue-bodies` Makefile:1141 |
| Hand-authored issue | NO (review standard only) | no live gate — BUT a bold-headed `**Acceptance criteria:**` (no `## `) defeats BOTH `issue_body.section_body` (parses ZERO criteria, gate returns green) AND `acceptance_writeback.tick_acceptance` (raises `BodyError: no ## Acceptance criteria section`), so a verdict can never tick it (#1792 red). The criteria section must be canonical `## ` heading for any tick/gate path to work — form is load-bearing here, see gap. |
| PR body | NO | `check_pr_hygiene` gates AGENTS/BASE/SYNC/closing/base only; `AGENTS_MANDATE` = "issue, fix, benefit", never a checklist |

## Gap that #1796 closes

- Producer-only enforcement → hand-authored issues and ALL PR bodies escape.
- #1792 (open, ci-pipelines) verifies merge-time criteria are TICKED; #1796 is the form/coverage sibling — a body that never HAD the boxes to tick is silent under #1792.

## Planner-lane behaviour

1. **Dispatch mandate:** every issue I hand to a lane is already six-section with tickable acceptance (planner review standard). Under this rule it is also EVERY PR body I drive toward: when a lane opens a PR, the body must carry `## Acceptance criteria` `- [ ]` checklist + `closes #<n>` adjacent, beside AGENTS/BASE/SYNC/closing/base.
2. **Refine:** a routine-refined issue carrying no tickable `## Acceptance criteria` (any author path) is a form defect — refine to add the checklist before handing on.
3. **CI validation:** if I am adding a gate, reuse `issue_body.missing()` and `acceptance_writeback.acceptance_items` (bytes `- [ ]`/`- [x]` only inside `## Acceptance criteria`, NEVER the `tick_acceptance` write-back which stays #1644).
4. **Out of scope / do not touch:** `issue_body.py`'s renderer, `acceptance_writeback`'s verdict-gated seam, #1088 merge/arm, `-h`/`--version`-vs-serve engine gate.
5. **Do not relabel #1088** — this is a form/surface rule, never a merge-blocker to owner approval.

## File one body without a checklist — visible classes

- Open a PR whose body has only AGENTS/BASE/SYNC/closing/base, no criteria → the #1796 form-gate (when landed) surfaces it.
- File/refine an issue with a bare `## Acceptance criteria:` heading and no `- [ ]` item → `issue_body.missing()` fails it (#745).

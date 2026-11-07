# Skill↔code parity gate (issue #1924)

## Problem

Nothing in the tree checks that a skill's documented mechanism matches the code's actual behaviour,
and the drift is measurable: the planner's live skill carries 249 references while `main` carries
104 (145+ live-only at the measurement), and the live `auto-merge-mechanism.md` §3 described the
pre-#1914 recheck bug as current behaviour.

## Proposal

Two gates. Layer A (`make skill-parity`, host-only, read-only) diffs each `agents/<profile>/skills/`
against the live profile's skills dir and reports live-only / tree-only counts+names, never syncing.
Layer B (`make check-skill-code-parity`, CI) asserts every skill reference's cited test id resolves to
a hermetic-suite test and every repository-owned backticked symbol resolves. It is a gate, never a
writer: it makes drift a red instead of a silent divergence.

The first correction it forces is `auto-merge-mechanism.md` §3 (post-#1914 behaviour), which is also
committed (it was live-only).

## Open questions / decisions

- A citation inside a fenced block is a quoted log/command, not a claim; it is not checked.
- A `...` test id suffix is abbreviation and resolves by prefix.
- `tests/test_x.py::test_name` is the generic template, not an anchor.
- External/vendored backticked tokens (`vllm/…`, a Hermes tool path) are environment, not this repo.
- The 145-file live→tree fold is out of scope (#791/#1062); this gate only makes it visible.

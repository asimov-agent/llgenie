# Wire the #1310 fold tool into the Makefile so check-wiring stops reddening (2026-11-01) — issue #1079

## The defect (introduced by my own #1310)

`agents/llgenie-tester`'s fold tool was versioned into `scripts/fold-live-profile.py` (#1310, merged
`e37513ba`) without being named by any make target or workflow. AGENTS.md's rule — "A new test file is
invisible until a make target names it" — extends to `scripts/*.py` via `scripts/check_wiring.py`: an
unwired document is an **ERROR** ("`scripts/fold-live-profile.py` is wired to nothing"). The next CI
scope run (on the #1312 head) reddened `make check-wiring` exactly there. A doc-only fold did not need
to also fix the tool's wiring; the tool's own vehicle had to.

## The fix (`make tester-fold-live`)

A row in the `.PHONY:` block and a target that runs the tool from the repo root, sibling to the other
profile-seam targets (`sync-agent-profile`, `profile-drift`):

```
tester-fold-live: ## Enumerate a described live host-agent lane against its tree copy; COPY=1 writes live→tree (PROFILE=<profile>; issue #1079) — host-only: a CI runner has no live profile to fold from
	@test -n "$(PROFILE)" || { echo "Usage: make tester-fold-live PROFILE=<profile> [COPY=1]"; exit 2; }
	python3 scripts/fold-live-profile.py --profile "$(PROFILE)" $(if $(COPY),--copy,)
```

Host-only by design (a CI runner has no live Hermes profile), matching how `profile-drift`/
`sync-agent-profile` are documented as host-only in `docs/BOTS.md` without a host-only-wiring entry —
they are wired by a make target, and check-wiring counts every target-named document as wired. The
tool itself already guards the two failure shapes: `--check` exit 1 on drift, and the deliberate
refusal (`exit 2`) while a live file is mid-write.

## Proof

`make check-wiring` (and the full `make check-docs` + `changes_index` + `census` + `lint_linefeeds`
chain) green at HEAD; `make find-help`-style verification that `tester-fold-live` now appears in the
`.PHONY` block.

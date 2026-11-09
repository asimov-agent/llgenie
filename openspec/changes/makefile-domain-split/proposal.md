# Makefile domain split — `mk/*.mk` + script entry points

Proposal to split the single 2,083-line `Makefile` (373 targets, 274 inline
`python3`/shell snippet lines at last measurement) into domain-scoped
`mk/*.mk` includes, teach the wiring gate to resolve the includes before the
split lands, move the five longest recipes' inline snippets into `scripts/*.py`
entry points, and add the duplicate-target + per-file line-budget gates so the
split cannot silently rot back.

## Why

Everything in the repository is reachable only through `Makefile`, and the
file is reviewed as one unit: two unrelated PRs touching two stages conflict
on it, a 30-line recipe cannot be unit-tested except through the gates that
already exist, and inline snippets carry real logic where no type checker,
no formatter and no test ever looks. `scripts/check_wiring.py:66` still
hardcodes `MAKEFILES = ("Makefile", "tools/Makefile")` read as text, so it
goes blind the moment a target moves. `docs/ARCHITECTURE.md` calls the
Makefile "the only entry point for every stage and gate; CI calls
`make <target>` and nothing else".

## What changes

1. **Teach `check_wiring.py` to resolve `include mk/*.mk` FIRST.** It currently
   reads `Makefile` and `tools/Makefile` as flat text. The gate must walk the
   top `Makefile`, follow every `include mk/*.mk` directive, and build its
   recipes/prerequisites/`.PHONY` graph from the concatenated text — so the
   split cannot make the gate go blind.
2. **Split the Makefile into `mk/{engines,gates,ci,security,bots,install}.mk`.**
   The top `Makefile` keeps only version/`help`/`.PHONY`/`DEFAULT_GOAL` and the
   `include` lines. **Target names and recipes are unchanged** — every
   workflow, doc and bot keeps working.
3. **Move the five longest recipes' inline snippets into `scripts/<stage>.py`
   entry points with unit tests.** A target becomes `python3 scripts/<stage>.py
   ...` with the snippet's logic (and exit codes) in a tested module.
4. **Add gates:** `check_wiring.py` fails on a target name declared twice
   across the includes, and each `mk/*.mk` file carries a line budget so the
   file cannot quietly grow back. `docs/ARCHITECTURE.md`'s claim is updated if
   the split changes it.

## Anti-goals

- No target name or behaviour changes.
- `check_wiring.py` is not weakened into always-pass.
- No stage's logic vanishes: logic moves to a tested module, never is deleted.

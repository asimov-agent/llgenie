---
name: ci-scope-engines-units-battery
about: a skills/engines dependency-pin change re-includes the linux/unit security battery
status: active
---

# `engines` class re-includes the `linux/unit` security + pin battery (issue #2227)

## Proposal

A `skills/engines/*/SKILL.md` edit is the GENERATOR of the
`containers/engines/params/*.json` pins that `engine_pins.py` inventories into the security SBOM.
But `scripts/ci_scope.py` classified the `engines` class to select only
`guard`/`ci-images`/`linux/lint`/`linux/install`/`linux/cpu-health` — and SKIPPED `linux/unit`, the
only job that runs `check-engine-pins-published`, `check-secret-output`, `check-proc-gate`,
`check-security-scan` and `check-actions`. A dependency pin or install string edited directly in an
engine skill reached `main` with none of the gates that exist to catch it.

## Motivation

Measured at `main@f2adaa80` (before), `python3 scripts/ci_scope.py --paths
skills/engines/vllm/SKILL.md`:

```
[ci-scope] class=engines
[ci-scope] job=linux/unit skip — no class from [engines]; needs one of scripts,tests,data,skills,containers,workflows
[ci-scope] scope: class(es) engines -> 5 of 10 job(s): guard,ci-images,linux/lint,linux/install,linux/cpu-health
```

`linux/unit` (`Makefile` `ci-unit:`) is the sole carrier of the five security gates; an `engines`-only
diff that skips it is a pin/secret edit that passes every green.

## Change

- `scripts/ci_scope.py`: add `"engines"` to the `_STAGES["unit"]` tuple so a `skills/engines/**`
  (or `containers/engines/**`) change re-includes `linux/unit`. Read-only classifier widening — it
  adds jobs a change must pass, never removes one (anti-weakening). `containers/engines/**` was
  already unit-selected via `containers/**`, so that re-inclusion is a verified no-op.
- `tests/test_ci_scope.py` + `tests/test_ci_scope_trigger.py`: assert the `engines`-class skill path
  re-includes `unit`, the negative controls (a non-engine `agents/**` skill stays unit via `skills`;
  a `docs`-only change still skips), and a Makefile regression guard that the five gate targets live
  under `ci-unit:`.

## Acceptance

- [x] `python3 scripts/ci_scope.py --paths skills/engines/vllm/SKILL.md` prints `job=linux/unit run`.
- [x] The same command on a `agents/**` skill path still prints `job=linux/unit run` (via `skills`),
      and on a `docs/**` path still prints the skip.
- [x] `tests/test_ci_scope.py` and `tests/test_ci_scope_trigger.py` assert the re-inclusion and both
      negative controls (49 pass in `llgenie/test:latest`).
- [x] No gate is weakened: `git diff` touches only `scripts/ci_scope.py`, the two test files and this
      change dir (no `data/security-policy.json`, no workflow, no scanner config).

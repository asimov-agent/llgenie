# engines class re-includes the linux/unit security battery (issues #2227, PR #2348)

Implements issue #2227 via PR #2348 (`llgenie-security/2227`). A `skills/engines/*/SKILL.md` edit is
that `engine_pins.py` inventories into the security SBOM. Before this change `scripts/ci_scope.py`
selected only `guard`/`ci-images`/`linux/lint`/`linux/install`/`linux/cpu-health` for the `engines`
class — **skipping** `linux/unit`, the only job that runs `check-engine-pins-published`,
`check-secret-output`, `check-proc-gate`, `check-security-scan` and `check-actions`. A dependency pin
or install string edited directly in an engine skill reached `main` with none of the gates that exist
to catch it.

## The fix

`scripts/ci_scope.py` adds `"engines"` to the `unit` stage tuple, so a `skills/engines/**` (or
`containers/engines/**`) change re-includes `linux/unit` and therefore the full security + pin
battery. This is a read-only classifier widening — it adds a job a change must pass, never removes
one (anti-weakening). `containers/engines/**` was already unit-selected via `containers`, so that
re-inclusion is a verified no-op.

## Verification

Measured at the fixing head (`python3 scripts/ci_scope.py --paths skills/engines/vllm/SKILL.md`):

```
[ci-scope] job=linux/unit run — class engines
```

Negative controls: a non-engine `agents/**` skill still selects `unit` via the `skills` class, and a
`docs/**`-only change still skips it. `tests/test_ci_scope.py` + `tests/test_ci_scope_trigger.py`
assert the re-inclusion + both controls (49 pass in `llgenie/test:latest`), plus a Makefile
regression guard that the five gate targets live under `ci-unit:`.

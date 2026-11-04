# A vendored build-requirements file can be internally unsatisfiable

## Symptom
An engine image build fails in a build-requirements step, and (only once `_sh` prints the captured
buildx streams — see `docker-error-surfacing.md`) the error names a resolver contradiction:

```
uv pip install --system --break-system-packages -r {src}/requirements/build/<backend>.txt --index-strategy unsafe-best-match
  x No solution found when resolving dependencies:
     Because torch==<V>+<backend> depends on triton==<V>.<backend>
     and you require torch==<V>+<backend> ... and because you require triton==<V>,
     your requirements are unsatisfiable.
[engine-runner] FAIL <engine>/<backend>: step exited 1
```

Without the surfacing fix the job shows a bare FAIL with no resolver text, and the failure looks
like a toolchain/compile problem rather than a pin defect.

## Cause
The vendored upstream `requirements/build/<backend>.txt` pins TWO contradicting rows: a
backend-suffixed `torch==<V>+<backend>` whose own dependency requires `triton==<V>.<backend>`, plus a
BARE `triton==<V>`. uv finds no satisfying set — the file contradicts itself at that pin. Sibling
backends that pin only `torch` (no triton row) do NOT hit it, so ONE backend reds while the others
build — that asymmetry is the tell.

## Fix (in the SKILL install list, never the generated params JSON)
Normalize the stale pin inside the CLONE immediately before the build-requirements install:

```
- "cd {src} && sed -i 's/^triton==<bare>$/triton==<backend-suffixed>/' requirements/build/<backend>.txt && uv pip install --system --break-system-packages -r requirements/build/<backend>.txt --index-strategy unsafe-best-match"
```

Edit `skills/engines/<engine>/SKILL.md`, regenerate with
`python3 scripts/engine_skills.py params --only <engine>`, prove no drift with
`… params --only <engine> --check` → must read `0 file(s) stale`, and commit the SKILL and the
regenerated `containers/engines/params/<engine>.json` together. A `check-engine-params` gate
reverts a hand-edited JSON, so the JSON is DERIVED — never edit it directly.

## General rule
A vendored upstream requirements file is upstream's to define and can be internally inconsistent at a
given pin. Diagnose from the resolver error (it names the two contradicting constraints), then
normalize ONLY the stale pin inside the clone at install time, driven by the skill. Do NOT "fix" it by
pinning a different torch (that shifts the whole engine×arch matrix and every image tag) and do not
touch the committed JSON.

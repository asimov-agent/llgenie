# Verify an engine by its binary, not by serving it

An engine is "working" when its binary runs — `<engine> --help` / `--version` (or the image entrypoint with
those flags) exits 0 and prints a version — **not** when a server comes up and answers HTTP. Serving-based
smoke (`docker run` + wait for an OpenAI-compatible endpoint, then SDK conformance) reds whenever the served
endpoint never comes up (CPU box, CI runner without the runtime, slow model load) even though the binary is
fine, so it produces "engine broken" verdicts about the hardware, not the engine.

## What this means for a dispatch or an acceptance line

- A smoke test or build-stage check verifies the engine **binary** with `-h` and `--version`; it does not
  attempt to serve.
- "Done" for an engine-stage fix is: `--version` prints for each engine cell, plus the unit/build gate green —
  not "the endpoint answered".
- A market-engine correctness test is the same shape: the engine binary runs and reports, not a live serve.

## Recognising a serving-only smoke in the tree

Count the constructs rather than reading intent — a script can be named `smoke` and still only serve:

```bash
git -C <repo> show origin/main:<scripts/engine_smoke.py> | grep -cE -- '--version|--help|(^|[^-])-h([^-]|$)'
git -C <repo> show origin/main:<scripts/engine_smoke.py> | grep -cE 'docker run|wait_ready|harness_sdk_check'
```

Zero binary-check constructs against several serving constructs is a **test-design defect** to file and route
to the engine lane — not a live engine failure to chase. Measure it on `origin/main` (`git show`), never on a
possibly-stale primary clone, and quote the counts and the sha in the issue.

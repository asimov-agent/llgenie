# Engine-build cell verification: serve-vs-flags is CAPABILITY-driven, never a blanket rule

**Trigger:** an engine-build matrix cell reds on a serve / host-verify leg, or the owner says "engines are only
meant to verify the binary (`--version`/`-h`), not serve it". Do NOT take that as "remove all serving from the gate" —
read it as *serve on the arch the engine actually supports, flags-only otherwise*.

## The rule

Whether a cell serves or only checks the binary is decided per engine×arch by the canonical capability manifest,
never by a blanket policy:

- Manifest: `data/engine-capabilities.json` → `engines.<id>.archs` (issue #1214; this field is the documented set
  of backends the engine's upstream actually supports serving on).
- A cell whose engine `archs` **includes** the cell's arch → **must serve** (serve-leg `test-published-engine` +
  host-verify `test-engine-host`, `make test-engine-stage TEST=serve`).
- A cell whose arch is **not** in the engine's `archs` → **binary flags only** (`-h`/`--version`, the default
  `scripts/engine_smoke.py` contract, issue #1717) and it is green on flags — never forced to serve.

```bash
# decide from the manifest, not a guess (read at origin/main, never the stale clone)
git -C <repo> show origin/main:data/engine-capabilities.json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["engines"]; print({k:v["archs"] for k,v in d.items()})'
# examples that pin the two buckets:
#   mlx.archs=[metal,cuda,cpu]  -> mlx-cpu IS serve-capable
#   webllm.archs=[]             -> flags-only
#   tensorrt-llm.archs=[cuda]   -> cuda serve-capable, others flags-only
```

## Three buckets — classify the red before dispatching a fix

1. **Capable cell, serve-path failure** → the engine CAN serve this arch, so a red here is a real serve defect
   (probe timing, model-load, retry budget) to FIX on the serve test — never de-scoped. Signal: the image built,
   published and the engine **started and reached READY**, then the chat probe errored (`TimeoutError` in the
   probe, e.g. `engine_host_test.py` chat-probe). A READY-then-probe-timeout is a serve-PATH defect, NOT evidence
   the engine cannot serve — do not reclassify it as "capability absent" and skip it.
2. **Non-capable arch** → binary `-h`/`--version` only; green on flags. If such a cell reds, the red is a real
   binary/flag defect, not a serve issue.
3. **Build-level failure** (dependency resolution, `poetry` under `--no-build-isolation`, a skip guard printing
   `SKIP …` yet still exiting non-zero, image build) → its own defect lane; it is neither serve-vs-flags nor a
   capability question.

## Pitfalls

- **A blanket "never serve in the gate" fix is wrong.** It de-scopes capable cells that must serve (e.g. `mlx-cpu`
  declares `cpu`) and hides real serve defects behind a flags-only pass. The owner's correction is conditional on
  the arch, not absolute.
- **Conversely, serving an unsupported arch is a guaranteed red.** Forcing `serve` on an engine×arch it does not
  support reddens the matrix for a reason unrelated to whether the engine works — the mirror-image error.
- **"started + READY, probe timed out" ≠ "cannot serve".** Read where the red sits: a probe timeout after READY is
  a serve-path fix on a capable cell; only a cell whose arch is absent from `archs` is a genuine non-serve case.
- **Key the serve-vs-flags decision in the workflow to the manifest `archs`**, so the criterion is quotable and
  survives new engines/archs landing — do not hardcode a per-engine serve list in prose or a second table.

Route the workflow change (`engine-build.yml`: serve-leg, install-leg, host-verify) to the CI-pipelines lane that
owns it; keep a capable-cell serve failure as a serve test criterion, not a de-scope checkbox.

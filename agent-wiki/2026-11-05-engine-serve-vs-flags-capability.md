The engine-build workflow's per-cell serve-vs-flags decision (issue #1748).

Every cell first proves the engine binary answers -h/--version (the default gate,
issue #1717). Serving conformance (`serve-leg`, `host-verify`) runs ONLY on cells
whose engine declares the cell's arch in data/engine-capabilities.json
`engines.<id>.archs` (issue #1214). A cell whose engine does not declare the arch
is binary-flags-only and never runs a serve assertion. mlx-cpu (capable:
`mlx.archs` includes `cpu`) is NOT de-scoped — it stays a serve test; its probe
red at run 41957934540 is a serve-path defect tracked separately.

| engine | arch | declared? | verdict |
|---|---|---|---|

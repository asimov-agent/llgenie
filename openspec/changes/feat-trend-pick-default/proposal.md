# llgenie: interactive trend pick by default, vendored registry, manual mode (issue #105)

## Why

After #101 every inference server is a CI-tested GHCR image and `llgenie --pick` can rank
models and engines, but the trend data is opt-in, fetched live from
`raw.githubusercontent.com` on every run (not reproducible, CI tests a different file than
users get), cannot be synced with make, and the download only works when the registry's
`hf` repo itself holds `.gguf` files (11 of 14 models point at the base safetensors repo).
`make install` never exercises the trend flow.

Issue: #105. Parent: #92. Builds on #98 / #102 (PR #101).

## What Changes

- `data/models.json`: verbatim copy of `andyholst/trending-local-llms@master:data/models.json`,
  the default registry (`LLGENIE_REGISTRY_SRC` still overrides). No live fetch at run time.
- `make sync-registry` (download + validate + write when changed), `make check-registry`
  (validate; CI `unit` job). `scripts/sync_registry.py`, stdlib only.
- `.github/workflows/registry-sync.yml`: daily + `workflow_dispatch`, runs
  `make sync-registry`, `make skills-validate REGISTRY=data/models.json`, `make test-unit`, and
  opens/updates a PR from `chore/registry-sync` when the file changed. Never merges.
- `llgenie` with no model argument = interactive trend pick:
  1. exactly the upstream README "Most loved" list, in README order, every model whose VRAM
     column fits the card; rows that cannot be served here stay, marked with the reason;
     `[local]` marked;
  2. the compatible engines of the chosen model, t/s measured on this host's hardware first;
  3. reuse a local file or resolve a GGUF repo on the Hub (registry repo, else the
     most-downloaded `<name>-GGUF` repo, same org first) and download the largest GGUF that
     leaves ~15% of the card free;
  4. serve through `~/bin/llgenie-engine-<id>` as `llm-local`.
  `--auto` / no terminal takes the top model and engine. `--local` keeps the old local picker.
- Manual mode: `llgenie --engines [model]` lists engines (all, or compatible with a local or
  registry model); `llgenie <local> --engine <e>` and `llgenie --pick <model> --engine <e>`
  serve that pair only when compatible (image variant for this host + skill `formats`
  include the model format), else exit non-zero naming the compatible engines.
- Tests after `make install`: `test-install-ci` runs the trend flow from the installed
  `~/bin/llgenie` in a pty and serves a real downloaded pick that answers "hi";
  `test-install-published` runs the pty trend flow (`--dry`) per backend.
- README: trend flow, manual mode, `make sync-registry`.

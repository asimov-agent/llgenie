# Fleet plugin parity: give every lane the planner's plugin set

Goal: every `llgenie-*` profile carries the same plugin set as `llgenie-planner`
(`advanced-delegation`, `hindsight`, `memory-wiki`, plus bundled `nerve`).

## Procedure

1. List the source of truth:
   `ls -d ~/.hermes/profiles/llgenie-planner/plugins/*/` and
   `sed -n '/^plugins:/,/^[a-z_]*:/p' ~/.hermes/profiles/llgenie-planner/config.yaml`
   (keep the `enabled:` list and `entries:` block as the parity target).
2. Pin: read revisions from `plugins/.install-metadata.json` in the planner.
   Never install a floating HEAD — pass `--ref <40-char-sha>` so all lanes match.
3. Target profile = `HERMES_HOME=$HOME/.hermes/profiles/<profile>` for the
   `hermes plugins` subcommands; there is no global `--profile` flag.
   ```
   cd /tmp && HERMES_HOME=$P hermes plugins install <id> --ref <sha> --yes-deps --enable
   ```
   Run it under `terminal(background=true)` — 3 plugins x 12 profiles is ~10 min
   and the foreground cap is 600 s. Re-run the script; it skips present dirs.
4. Verify from disk, not from the install banner:
   - dirs: `ls -d $P/plugins/*/`
   - pins: `.install-metadata.json` revisions equal the planner's
   - enabled: `awk '/^plugins:/{f=1} f&&/^  enabled:/{g=1;next} g&&/^    - /{print $2}' config.yaml`
   - live: `HERMES_HOME=$P hermes plugins list --plain | grep <name>`

## Pitfalls (measured)

- **`memory-wiki` is not the catalog id.** The install fails with
  "not in the Hermes plugin catalog"; the catalog entry is `hermes-memory-wiki`
  while the on-disk directory and enabled name stay `memory-wiki`. Planner
  metadata records `"catalog": {"name": "hermes-memory-wiki"}`.
- **`hindsight` installs but does not auto-enable**, even with `--enable`; it is a
  memory-provider plugin awaiting a provider choice. Follow up with
  `hermes plugins enable hindsight` (prints "already enabled" when the first
  attempt did land).
- **Installing `hindsight` writes `memory.provider: 'hindsight'`** into that
  profile's config.yaml — a behaviour change beyond "same plugin set". The
  planner itself runs `memory.provider: ''`, so restore `''` after install
  (`sed -i "s/^  provider: 'hindsight'$/  provider: ''/"`) to reach true parity,
  and say so in the report.
- `hermes plugins list --plain` files git/catalog plugins under the fourth
  column, so `$4` is the plugin name and `$1` is `enabled` / `not enabled`.
- Each successful enable prints "Gateway reloaded plugins" — the running
  gateway picks the plugin up without a restart.

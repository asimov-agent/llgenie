# No secret VALUE reaches a log or an environment (agent-image & bot CI)

Guard every key, not just the one a previous PR happened to touch. A provider key gets its own
redaction + tests; every OTHER key ships by the same rule and is one line from breaking — an echo of
a token variable, a `set -x` in a script that reads a key, or `${{ secrets.X }}` interpolated into a
`run:` block instead of `env:`. For the guard that scans the whole repo (`scripts/check_secret_output.py`),
the six named rules, and the measurement commands, see `references/secret-value-guard.md`.

## The standing rules

- **GitHub masking is NOT a guarantee.** It filters the log *stream*, so a transformed value
  (base64, URL-encoded, a slice) sails past it, and nothing at all is masked in a log the job uploads
  itself. A value on a command line (`-e KEY=$KEY`, `--build-arg KEY=$KEY`) is public to every
  process on the runner via `ps`, not just to the log.
- **Pass the NAME, never the value.** `docker run -e KEY` (name only) — the runner's env supplies the
  value; `-e KEY=$KEY` embeds the value in argv. Same for `--build-arg KEY=$KEY`.
- **A commit that references a number labels a PR, not an issue, when the number IS the PR.**
  README/wiki headers like "(issue #283)" are wrong when #283 is the PR that fixed it — label it
  `(#283)` the way the repo labels PR citations, no "issue".
- **A guard that exempts the thing it checks is not a check.** Exempt only what is genuinely a test
  fixture (and mark it visibly, e.g. a `secret-output: test value` line) plus the guard's own source
  and its test — nothing else.

## Verify secrecy in the artifact, not the Dockerfile

Proving "the value is not exposed" means MEASURING the published image the bots actually run, not
reading the build config:

```bash

# the image's own config ENV carries no KEY/TOKEN/SECRET entry
TAG=ghcr.io/<org>/<repo>/agent:<sha>
docker image inspect "$TAG" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -iE 'KEY|TOKEN|SECRET' || echo none

# no key VALUE inside the image filesystem; the runtime .env holds only non-secret settings
docker run --rm "$TAG" bash -lc '
  grep -rIl -E 

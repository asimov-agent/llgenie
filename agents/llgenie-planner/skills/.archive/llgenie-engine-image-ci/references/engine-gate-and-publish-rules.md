# The engine gate, the publish path, and how to audit a green sweep

Depth for the rules a green row must satisfy, plus the recipe for reading a sweep row by row instead of
trusting its colour. Load this when a sweep looks "all green" but the engines were never really proved, when
a detect/flag change has to land, or when an engine matrix job fails on permissions.

## The gate (`scripts/engine_image.py`)

| rule | code | what it means |
|---|---|---|
| at least one flag exits 0 | `decide(...)` | `--version`/`-V`/`--help`/`-h`; one working flag never vouches for a dead one, but SOME flag must answer |
| `probe: device` is not an exemption | `DEVICE_ONLY` | only a cell named there passes with every probe failed; each entry carries the measured reason |
| a version must be a version | `version_proof()` | semver (`0.5.21`, `0.32.0+cpu`, `0.7.0-dev`) or `pin <sha7+>`; a log stamp and `0.0.0` are refused |
| the detect proves it | `test_image()` | `entrypoint.sh detect` output is parsed by `version_proof`, and the failure names what it saw |

Census without building anything: `make engine-gate-report` → per cell `flag-proven` / `device-exempt` /
`disabled`, its documented flags, its policy, and the `detect` line the gate will judge.

## When a detect or flag change will not take effect

The image tag is `llgenie/<id>:<pin8>-<hash8>-<variant>`, and `_image_inputs()` hashes the variant's params
(including `detect` and `binary_flags`) plus the committed Dockerfile, `entrypoint.sh` and `engine_runner.py`. So:

- editing `detect`/`binary_flags` → new hash → `_available()` misses on GHCR → a real build runs, and
  `make check-engine-params` must be green after `make generate-engine-params ENGINE=<id>`;
- editing only prose in a SKILL.md → the rendered params are unchanged → same tag → nothing rebuilds;
- an EXISTING tag being pulled (`available -> no rebuild`) proves the published artifact, not that the
  Dockerfile still compiles today: a moving `FROM` tag or a dead package index stays invisible. `FORCE=1`
  forces the compile; a dispatched sweep only verifies unless `push=true`.

## Publishing: which head can run green

`ci.yml` builds the cells a PR **changed** and then runs `make push-engine` on every pull_request. A fork head
has a read-only token, so those jobs fail at the push with
`denied: installation not allowed to Write organization package` — after the build and the gate passed, which
reads like an engine failure and is not one. Consequences:

- engine params / Dockerfile / detect changes ship from a branch **in the upstream repo**;
- check runs are attached per sha, so a failed fork run keeps a sha red even after a same-repo run passes it —
  move to a same-repo head with a **fresh commit**, not the same tree;
- `engine-build.yml` only publishes when `push=true`, so a full sweep verifies without needing write access.

## Auditing a sweep row by row

`gh run view --job <id> --log` refuses while the run is still in progress, but the API serves logs for a
completed JOB:

```bash
gh api "repos/<owner>/<repo>/actions/jobs/<job-id>/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' \
  | grep -aE "entrypoint detect|OK image test|FAIL|exempt|: NO ANSWER|: answers ->"
```

Classify every row into one of three buckets before believing the sweep:

1. **flag-proven** — a documented flag printed `answers ->` (exit 0) and `detect` proved a version;
2. **device-exempt** — every probe said `NO ANSWER (exit 1)`, the row is on `DEVICE_ONLY`, and only `detect`
   proved a version. Green, but it proves the FILE exists, not that the CLI runs;
3. **hollow** — `detect` printed a log stamp, `0.0.0`, or a daemon warning. Under the strict gate this is a
   failure; if it is green, the gate is not the one described above.

Then confirm the fix on a GPU host (see SKILL.md): a hosted runner cannot prove a device-only cell.

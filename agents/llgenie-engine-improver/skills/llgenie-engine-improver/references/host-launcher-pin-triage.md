# Host launcher-pin triage (`check-engine-launchers`)

Load when `make check-engine-launchers` reds on this host, or a launcher points at an image that will
not pull. The red has TWO different causes and they belong to different lanes — classify before you
write anything, because "stale launcher" and "unpublished pin" produce the identical symptom.

## The measurement, in order

Run from a worktree at the freshly fetched `origin/main` (the committed params are the expectation):

```bash
# 1. what the installed launcher actually carries
make check-engine-launchers            # prints e.g. 9 ok, 1 stale, 2 missing (arch cuda)
#    and, per stale row:  launcher pin=<old> params=<oldp> -> expected pin=<new> params=<newp>

# 2. the expected pin from the committed params
python3 -c "import json;print(json.load(open('containers/engines/params/<id>.json'))['pinned'])"
```

`missing` rows for engines whose images were never published for this arch are **informational** —
do not count them as defects and do not try to "fix" them. Only `stale` rows are the work item.

## Classify: pin moved vs one of the tag's FOUR inputs moved

The tag hashes the variant's params, its committed Dockerfile, `containers/engines/entrypoint.sh` and
`scripts/engine_runner.py`. If `params` digest in the expected tag differs from the launcher's, the
params moved; if only the pin differs, the pin moved. Either way the launcher is behind — but say
which, because "another input moved" is not a pin bug.

## Is the expected pin actually published?

**Probe with a per-repo pull token and a GET, or with the real pull.** Two ways to get a wrong answer:
`HEAD https://ghcr.io/v2/.../manifests/<tag>` is not reliable on GHCR, and a token that lacks the ghcr
package scope answers `403` for BOTH a published and an unpublished tag. The discriminating probe is
`GET` with a *per-image-repo* anonymous pull token — `scripts/ghcr_publish_probe.sh <leaf> <tag>` does
exactly that and maps 200=PUBLISHED / 404=ABSENT / anything else=UNKNOWN-retry (comma-joining two repo
scopes in one token returns 403, so fetch one token per image). The authoritative check remains the one
the installer itself performs:

```bash
make engine-launchers ENGINES=<id>     # resolves the exact tag, then docker pull
# [engine-image] $ docker pull ghcr.io/asimov-agent/llgenie/<id>:<pin>-<params>-<arch>
# [install] FAIL <id>/<arch>: not published in ghcr.io/asimov-agent   <- the real verdict
```

`FAIL ... not published` = the CI cell has not published this tag. That is a **publish gap owned by the
pipeline lane**, not something this host can repair, and never a reason to build locally.

## What each outcome owes

| Outcome | Action |
|---|---|
| stale, expected tag **published** | `make engine-launchers ENGINES=<id>`, then re-run `check-engine-launchers` for rc 0 and once more for idempotency |
| stale, expected tag **not published** | file an issue for the publish gap (see `references/issue-filing.md`); the launcher legitimately stays on the old pin until the cell publishes |
| several engines fail to pull | refresh the ones that CAN advance, and report only the unpublished remainder — never let one blocked engine hold the rest |

Copy the failing launcher and its check output to `/tmp` before you rewrite anything: the stale file is
the evidence an issue or review cites.

# Fork PRs cannot publish (or validate) a new CI image hash

## The symptom chain

A PR proposing a change to a CI-image Dockerfile (`containers/test/Dockerfile`, `openspec/Dockerfile`)
reds `ci-images`, and then reds `scope.yml`'s docs gate on the same hash. The build itself is fine:
a local single-arch and a multi-arch **no-push** build of the same Dockerfile both succeed.

## The mechanism

A `pull_request` run whose head is a **fork** (`isCrossRepository: true`) gets a `GITHUB_TOKEN`
scoped **read-only** to the base repository's GHCR packages. `permissions: packages: write` in the
workflow does not change this — it is a GitHub platform rule, not a workflow setting. So:

1. `scripts/ci_images.py::publish()` runs `docker buildx build --push` unconditionally; the registry
   denies the push after the full multi-arch build (~30s).
2. The new tag (e.g. `openspec:<dockerfile-sha>`) therefore **never exists** — verify with
   `docker buildx imagetools inspect ghcr.io/...:<tag>` → "not found".
3. `scope.yml`'s docs gate then runs a strictly-pull target (`make openspec-image-pull`) on a hash
   that cannot exist, and reds independently of the first failure.

No PR from a fork can ever land a CI-image Dockerfile change until this is fixed.

## Diagnosis checklist (do these before blaming the Dockerfile)

- `gh pr view <n> --json headRepository,headRepositoryOwner,isCrossRepository` → is it a fork?
- `gh run view <run> --json repository,headRepository` → which repo did the run belong to?
- `docker buildx imagetools inspect <registry>/<image>:<tag>` → was the hash ever published?
- Scan the job log for **any** successful push in that run. Buildx progress lines are often
  masked/suppressed on CI (non-TTY stderr); an empty ~30s gap before `make` exits is the denial,
  not a silent hang. The absence of a successful push anywhere in the run is the proof.

## The fix contract (already solved for engines)

`scripts/engine_image.py::push` handles this for the engine image (issue #155): inside a
`pull_request` run a registry **write denial** (`WRITE_DENIED`) is a loud `::warning` skip (exit 0)
— *the image is built here; the run that lands the change publishes it* — while a same-`push`-run
denial or any other push failure still fails. It is locked by `tests/test_ci_publish_scope.py`.

Mirror that in `ci_images.py::publish()`:

- Capture the `buildx --push` output; on a permission denial **and** `GITHUB_EVENT_NAME == pull_request`,
  emit a `::warning title=publish skipped::` and return 0.
- On a denial in a `push` run, or any other non-zero push, fail loudly (return non-zero with a
  `FAIL` line, as the engine path does).
- Make the scope gate use an **ensure** target (`make openspec-image`, pull the published hash else
  build the change's own Dockerfile) instead of the strict-pull target, so a fork PR whose hash
  cannot yet exist is validated against its own image rather than red.

## Regression tests

Drive `publish()` with the literal GHCR denial string through the fake-docker seam in
`tests/test_ci_images.py`, three cases: skip on `pull_request`, fail on `push` for the same denial,
fail on a non-permission error in a `pull_request` run. Then **prove the guard catches the bug**:
neuter the skip (return the denied rc), watch the fork case fail, restore, watch it pass.

## Checking the shape you changed

Switching the scope gate from a pull target to an ensure target changes the **make target / step
name** the workflow runs. Grep the test tree for the old target spelling (`openspec-image-pull`, the
job step name) before pushing — a suite that asserts the old command words will red a correct fix.

Two follow-ons that the pull-vs-build switch does NOT surface as a red:

- **A heuristic matching set in a wiring test silently loses the re-spelled member.** A test that
  collects "jobs that pull a CI image" with `"-pull" in run` drops the job now calling the ensure
  target, and the ci-images dependency assertion quietly stops covering it — green, guarding nothing.
  Broaden the predicate to both spellings (or assert the membership by name) and prove it by
  re-planting. See `pitfalls.md` *a substring/heuristic candidate set can silently lose a re-spelled
  member*.
- **The fix extends to EVERY consumer, and each one drags doc drift.** `scope.yml`'s docs gate AND
  `pipeline.yml`'s `linux / openspec` both consumed the strict-pull target; fixing only one leaves the
  other red on the same unpublished hash. And the docs of record that describe the old "every job runs
  `make openspec-image-pull`, which fails instead of builds" behaviour (`docs/BOTS.md`, `AGENTS.md`,
  the Makefile comment) are now stale in the same commit — update the live sentences and leave the
  dated history (a merged openspec change's spec, a wiki note) untouched. **`AGENTS.md` is a protected
  agent-instruction file: a write there is refused without the owner's consent — do not retry or route
  around it; report the drift to the documentation lane instead.** The now-unused strict-pull target
  stops being a CI consumer and must shed any `## CI:` help-line claim or `check-wiring` reds it.

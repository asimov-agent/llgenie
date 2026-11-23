# Cache-write probe asks the package, not the cache ref, so buildcache namespaces can seed (issue #3017)

Date: 2026-11-23. Issue: #3017. OpenSpec change: `cache-write-package-probe`.

## What was verified
- The gap is measured, not inferred: post-#2912 build runs `44404039696` (job `135154515704`) and
  `44925052309` (job `136909270729`) both print
  `registry cache ghcr.io/asimov-agent/llgenie/edge0:4a7964de-874f7c96-cuda-buildcache absent -> cold build (cache write skipped; #1880)`,
  and the live GHCR tag list for `asimov-agent/llgenie/edge0` (`4a7964de-16ec5d83-cuda, cuda, latest,
  4a7964de-874f7c96-cuda`) carries no `-buildcache` tag. A never-seeded cache ref answers the read
  probe NO forever, so the write could never seed.
- `scripts/engine_image.py` now has `_tags_list_http` + `_package_published` beside `_digest_http`:
  anonymous GHCR pull-token exchange (`scope=repository:<package>:pull`), then
  `GET /v2/<package>/tags/list?n=1` — measured live 2026-11-23 against a published package (200 +
  tags) and an unpublished package name (404). Fail-closed: empty tag list, 404, unset `REGISTRY`, or
  a registry that stays unreachable after the retries all mean "not published" (today's skip).
  A 404 is a verdict, so it is not retried; only transport failures retry (5 s / 10 s backoff, the
  issue #3007 discipline).
- `_cache_write_args` is a ladder, not one shared probe: cache ref present → `--cache-to` unchanged;
  absent + package published → `--cache-to …,mode=max` with the note `absent -> seeding it (package
  published)`; absent + package absent → no `--cache-to`, the existing `cache write skipped; #1880`
  note. Read side (#1842) untouched.
- Probe budget holds: `_buildx` probes the cache ref once and threads it into both sides; the package
  probe runs only where a write is being decided AND the cache ref is absent, at most once per build.
  Forced and read-only builds consult neither (pinned by a probe that raises if called).
- Tests (`tests/test_engine_force_rebuild.py`): the six #1842/#1880 tolerance tests now stub the
  package probe ABSENT (their intent stays pinned), the #1880 cache-ref probe-contract test and the
  present-cache test stub it as must-not-run; 10 new hermetic tests cover the ladder (direct +
  push branch + `CACHE_WRITE=1` local branch), the
  probe budget, and the transport contract over a stubbed `urlopen` (tags → True, empty/404 → False
  with no retry, `URLError` → retried then answered / fail-closed after 3 attempts, no `REGISTRY` →
  no request). Targeted battery `pytest tests/test_engine_force_rebuild.py
  tests/test_engine_cache_namespace.py tests/test_engine_image_matrix.py tests/test_engine_skills.py
  tests/test_engine_bump.py` rc=0, zero network.

## Key decision
Write eligibility is a separate registry question from read eligibility: "does the cache tag exist"
vs "does buildx have a package to create the cache tag under". The seeding answer comes from the
package's tag list, which is what the #1880 hard `not found` actually depends on. Both notes stay
printed (#1796), and the failure mode stays fail-closed so a Hub blip can never redden a cell.

## Current status
Implementation, tests, OpenSpec change and docs on branch `feat/cache-write-package-probe`; unit
battery and lane gates run at the branch head. Live proof of the export (a build log showing the
cache push at rc=0, and #2891's AC2 warm replay under 20 min) needs the next engine-bump wave and
stays tracked on #2891 / #3004 — engine image builds belong to CI.

# Tasks

- [x] 1. `bump()` writes the `agent-wiki/<date>-engine-bump-<id>.md` note and its
      one-row `docs/changes.d/<date>-engine-bump-<id>.md` fragment, and rebuilds
      `CHANGES.md` from the fragments (`changes_index.write`), so the same commit
      that moves the pin carries the note pair `make check-docs` owes it (issue
      #1123).
- [x] 2. `bump()` recomputes the frozen image-hash asserts its own pin move makes
      stale (`es._image_hash(params, "<variant>") == "<8hex>"`, issue #2386) from
      the regenerated params and rewrites the `==` literals in `tests/` and
      `docs/` — a `!= "<hash>"` moved assert stays untouched. Only files that
      reference `params/<id>.json` are rewritten.
- [x] 3. The companion pair + image-hash rewrite are gated behind an explicit
      `emit_companions` argument to `bump()`: ONLY the lane entry points
      (`main`'s `bump`, and `bump_daily`, i.e. `make engine-bump`) set it, so a
      library caller driving `bump()` against a scratch tree never writes to the
      real repo.
- [x] 4. `.github/workflows/engine-bump.yml` adds an `OPENSPEC: publish-changed-pin-images`
      line to the bump PR body (issue #1807) and stages `agent-wiki/`,
      `docs/changes.d/` and `CHANGES.md` in the `git add` alongside the pin move.
- [x] 5. Unit tests with Given / When / Then cover the companion note+row pair, the
      frozen image-hash rewrite, and the body's OPENSPEC line + staging.
- [x] 6. `make test-unit` (the hermetic suite) passes; `make openspec-validate
      NAME=engine-bump-companions` exits 0.

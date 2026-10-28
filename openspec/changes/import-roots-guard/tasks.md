# Tasks

- [x] `scripts/check_import_roots.py`: the two rules, an `--allow` list, `check`/`report`/`ratchet`, `--update`.
- [x] The ratchet: counts may fall, may never rise; a missing baseline is a finding, not a pass.
- [x] `make check-import-roots` with a `## help` line, wired into `ci-unit`.
- [x] Negative control per direction: a path entry is refused, a bare import is refused; the conftest and
      a `from scripts.x import` are clean; an unparseable file is its own finding.
- [x] `docs/BOTS.md` names the target; `CHANGES.md` and an agent-wiki note record it.
- [x] The migration itself is **not** a task of this change: the guard lands first and the batches
      follow it, each reducing the recorded baseline.

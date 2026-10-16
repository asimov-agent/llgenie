# Tasks

- [x] 1. `_accepted_levels(run)` parses the guard's own `case` arm(s), skipping an arm whose line `exit`s (the refusal arm)
- [x] 2. `test_the_guard_checks_both_actors_and_a_write_level` asserts `accepted == {admin, maintain, write}` EXACTLY, naming the workflow and the set it actually accepts on failure
- [x] 3. `_guard_runs(path)` reads the guard step's own `run` text, so the `204` check cannot be tripped by an unrelated step mentioning `204`
- [x] 4. The negative direction is proven: `test_the_write_level_rule_reads_the_decision_not_the_prose` widens the real arm (asserting the replaced substring check PASSES it) and shows the reader rejects it, plus `read`/`triage`/`*` arms
- [x] 5. Falsified on the real tree: with `issue-bot.yml`'s arm widened to `admin|maintain|write|read` the suite is **2 failed, 5 passed** (the write-level rule now fails too; on `main` it was 1 failed, 5 passed)
- [x] 6. No file under `.github/workflows/**` touched — the eleven guard bodies stay byte-identical from #300
- [x] 7. README's trigger-guard section states the permission set is read from the `case` arm; `agent-wiki/2026-10-16-guard-write-level-arm.md` records the work
- [x] 8. `make lint`, `make check-docs`, `make check-wiring` and `make openspec-validate NAME=guard-write-level-arm` exit 0

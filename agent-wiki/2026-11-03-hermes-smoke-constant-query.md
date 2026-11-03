# hermes_smoke reads the newest unseen session with a constant query, not a formatted IN-clause (issue #1648)

`scripts/hermes_smoke.py::new_session` built its query by string-formatting the placeholder count into a
`WHERE id IN (...)` clause, which the daily semgrep scan reported as a `high`
`python.sqlalchemy.security.sqlalchemy-execute-raw-query` finding at line 80 — a false positive in
substance (this is the stdlib `sqlite3` driver on a read-only `file:...?mode=ro` store, never
SQLAlchemy, and the ids were always bound as arguments, never interpolated into the SQL), but the
rule fires on any formatted SQL string.

The function now issues a constant `SELECT id FROM sessions ORDER BY started_at DESC` and skips ids
already seen before the run in Python — the newest-unseen-session contract is unchanged (proved: the
repo's 10 `test_hermes_smoke.py` cases pass, behaviour identical for every before-set exercised; and
the fixed file reports 0 findings for the rule under the pinned semgrep image, `p/default`). The
commit is a real source fix, not a suppression annotation.

#1648

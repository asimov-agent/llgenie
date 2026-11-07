# Clearing a `security-scan` (semgrep) finding

`make security-scan TOOL=semgrep` runs the pinned semgrep image over the whole tree and
writes `security-reports/semgrep.json`. The daily job reds on any `severity: high` result,
so a security issue is "a real gate", even when the flagged code is not actually
vulnerable.

## Measure with the FULL scan, never a single-file scan

Scanning just the file you edited proves the rule can be silenced on that snippet; it does
not prove the gate greens. Run the real path on the worktree and read the report:

```bash
make security-scan TOOL=semgrep; echo rc=$?
python3 -c "import json;d=json.load(open('security-reports/semgrep.json'));
rs=d.get('results',[]);print('total:',len(rs));
[print(x['check_id'],'|',x['path'],x['start']['line']) for x in rs
 if '<your-path>' in x['path']]"
```

Expected leftovers: findings belonging to OTHER open security PRs (each Dockerfile fix is
its own issue/PR). Seeing a sibling file still listed is correct and must not be "fixed"
here — say so in the PR body so a reviewer does not read it as a partial fix.

## `dockerfile.security.missing-user`

Add a non-root `USER` line before the final `CMD`/`ENTRYPOINT`. The rule only inspects that
last identity, so the line is necessary and — when the Makefile overrides it with
`docker run -u root` — harmless.

**Choose the uid by who must WRITE.** A container whose `CMD` writes into a bind-mounted
host directory cannot use an arbitrary non-root uid: `USER 65532:65532` clears the rule but
fails to create `requirements.txt` in a `1000`-owned mount (permission denied, exit 1). Use a
named user whose uid matches the mount owner (`RUN useradd -m -u 1000 tooluser` +
`USER tooluser`); it clears the rule and the real invocation still writes. Prove BOTH:

```bash
make security-scan TOOL=semgrep        # finding gone for that path
docker run --rm -v "$PWD:/work" --workdir /work <img>   # the CMD still succeeds, file lands
```

Check the Makefile invocation first: if the container is always run with `-u root`, the
`USER` line is inert at runtime and no write test is needed.

## `python.sqlalchemy.security.sqlalchemy-execute-raw-query`

The rule fires on ANY `.execute(...)` whose SQL string is built by interpolation — `%`
formatting, f-strings, concatenation — even when only a **placeholder count** is formatted
and every value is passed as a bound argument. Two things to establish before choosing a fix:

- Is it even SQLAlchemy? A stdlib `sqlite3` connection on a read-only `mode=ro` store with
  values bound as args is a false-positive class. That justifies a *rewrite*, not a shrug.
- Prefer a genuine rewrite over a suppression. A query that must vary its `IN (...)` width can
  be replaced by a constant `SELECT ... ORDER BY <key>` plus the filtering in Python; the
  result set is identical and the rule has nothing to match. `# nosemgrep:` on the line
  immediately before the `.execute(` also clears it — use that only when no rewrite is
  behaviour-preserving, and say why in the note.
- Prove behaviour after the rewrite by running the file's own test module in the repo's test
  container (`tests/test_<name>.py`) — the rewrite is only acceptable if those stay green.

## Docs-classed paths: a Dockerfile change that can never publish

Before fixing a Dockerfile, check which `ci_scope.py` class its path falls in. Paths classed
**docs** (e.g. `openspec/**`) are in `ci.yml`'s `paths-ignore` and in the complement of
`_NON_DOCS`, so `ci-images` never runs — the new image hash is never published — while the
docs gate's `*-image-pull` step still tries to pull it and reds. That is a **gate
classification gap, not a defect in your fix**: no such change can go green. Report it, route
the classification change to the CI-pipelines lane, and do not churn the PR trying to make it
pass. A path that classes out as non-docs (`tools/**`, `scripts/**`, a wildcard) runs the full
`CI` normally.

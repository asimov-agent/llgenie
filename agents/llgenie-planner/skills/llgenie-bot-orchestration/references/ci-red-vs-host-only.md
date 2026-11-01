# Real ci-unit red vs host-only noise — measure before you dismiss

When a lane reports, or you observe, a failing unit test on `main` or a PR head, the first question is not "is this real?" but "does this test even run in CI?" Answer it with the fixture, never with the docstring.

## The check (do this before calling any red host-only)

```bash
cd <repo> && git show origin/main:tests/fixtures/unit-suite.json | \
  python3 -c "import json,sys;d=json.load(sys.stdin);\
print('test_x excluded?', 'test_x' in (json.dumps(d['excluded'])+json.dumps(d['deselect'])))"
```

- Not in `excluded`/`deselect` → it runs in the `linux/unit` leg. A red there is a REAL gate red that blocks every PR's unit leg on `main`. File a tracked issue to the owning lane; fix the drift.
- In `excluded`/`deselect` → genuinely not CI-visible; not a gate red.

## The trap: a docstring that says "host-only" is only half true

A test file whose docstring says its proof is *host-only* (`CHECK=1` against the owner's live `~/.hermes/profiles/...`, which a runner has no profile to satisfy) usually has **two halves**:
1. the `CHECK=1` live-profile half — cannot run in CI (correctly host-only);
2. a **tree-side** guard that runs unconditionally in the discovered suite — e.g. "a SKILL rule pointing at a `references/x.md` that was never committed is a finding."

Half 2 runs in CI. Dismissing the whole file as "host-only noise" because the docstring mentions `CHECK=1` is the repeated mistake — the tree-side guard is exactly what reds the unit leg. Read the test body for references/ SKILL/ tree assertions, not just the header docstring.

## Never silence by exclusion

Do NOT add a red test or a stale artifact to `unit-suite.json` exclusions/deselect to make a leg green. That converts a real drift into silent rot. The fix is the drift (fold the missing file into the tree, regenerate the stale rendered JSON), routed to the lane that owns the files.

## Two common red classes seen this way

- **Reference-integrity**: `SKILL.md` points at `references/<x>.md` that is live-only (absent from the tree). Fix: fold the file into the tree (byte-identical to live at branch time) or delete the dangling reference; regenerate nothing else.
- **Stale rendered artifact**: a committed `data/*.json` (e.g. a skill-gap or catalog render) no longer matches what the current code + registry produce. Fix: re-run the repo's own render path (never hand-edit), and prove the render is idempotent so it does not churn each sync.

## Evidence discipline

The failing-test list in a lane's *head verdict* is a claim; the `unit-suite.json` fixture + a clean-worktree reproduction is the evidence. Attributing a red to "pre-existing main drift from another lane" is only true after you have (a) confirmed the test runs in CI and (b) confirmed it reds at main independent of the reporting PR's diff. Then file it to the owning lane, not to the reporter.

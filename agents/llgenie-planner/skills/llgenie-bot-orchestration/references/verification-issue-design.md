# Designing the verification issue for a mechanism change

The owner's standing ask: when a change alters **which work the pipeline does**, the issue that ships it must carry a
companion issue that proves it with real changes, one per class of file, and the architect / implementer / tester
split the work. A design that is only asserted in prose is not shipped.

## Why a companion issue, not an acceptance bullet

A selection mechanism — path filters, class gates, skip lists, required-check wiring — is invisible in a green run. A
PR that runs 5 of 22 job families and a PR that should have run 22 but ran 5 both look green. The first version of
such a change usually ships a filter wider than the class it means to select, and the only case anyone exercises is
the easy one, where the bug cannot appear.

## Shape

One issue, one table, three roles:

| role | produces |
|---|---|
| architect / designer | the **expected** column, derived from the classifier code, never from the workflow YAML |
| implementer | the probe diffs: one branch per row, draft PR, closed unmerged after evidence |
| tester | the run ids and the per-row verdict |

**Expectations from the code, not the YAML.** If both sides are read from the same file the test agrees with the bug.
Run the classifier directly (`python3 scripts/ci_scope.py jobs --paths <p> --json`) and paste the measured counts into
the table before any probe runs.

## Row set

- **One row per class**, each a *single representative file*, cheapest possible edit (comment or whitespace):
  docs tree, docs root, generated notes, openspec, skills, agent profiles, workflows, scripts, tests, data,
  containers, engines, security, and each wildcard input.
- **A row for the file that is not what it looks like** — markdown under `data/`, fixtures under `tests/`. This is the
  row that catches an extension-based filter, and it is the row nobody thinks to write.
- **Negative controls, stated as expected behaviour, not as prose:**
  - unclassifiable path → the classifier **fails closed**: it selects the **full** set *and* exits non-zero. Over-selecting is the safe half; the non-zero exit is the alarm. Check it on **every** entry point the tool exposes — a `classify` that widens and exits 0 beside a `jobs` that reds means the verdict depends on which subcommand the workflow calls. Compare exit codes, not messages, and include the empty-argument case (`--paths ''` must behave like no `--paths`);
  - mixed diff → the **union** of the classes, never the smaller;
  - empty diff / classifier error → the **full** pipeline (fail open, never fail closed);
  - `push` to the default branch → unfiltered, always everything;
  - a deliberately broken gate on a non-required check → record `mergeStateStatus` **and** the auto-merge verdict,
    so "a red check is advisory" becomes measured instead of quoted from GitHub docs.
- **A row for the step that cannot be one file** — a version bump that must rebuild only what changed and publish
  both a new content-hash tag and a moved `latest`, proving both resolve. Name the issue that owns the tag mechanics
  and say that a gap there is a finding, not scope creep.

## Proof discipline

A row is proven by a **fresh completed run id at the probe's head** (`gh run view <id> --json status,conclusion,headSha`).
`queued` is no verdict, `cancelled` is no verdict, and "green locally" is not a row. The issue is only closeable when
every row has a run id or a written reason it cannot be run.

Two probes at a time maximum: each probe re-queues a matrix, and a queue longer than the runner pool converts verdicts
into cancellations — which is the exact failure the mechanism exists to prevent.

## Probe hygiene

- Draft PRs titled `probe: <class>`, no `closes` keyword, never merged, closed and branch-deleted after the evidence.
- Probes are throwaway artifacts in the owner's repo; say so in the issue so nobody reviews them as product.
- Re-verify the implementation PR's own invariant while the probes are queued (two trigger lists identical, guard red
  when broken) — that is a real measurement instead of a run counter.

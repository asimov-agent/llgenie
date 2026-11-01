# Security — supply chain

This page is the reference for what this repository pins, how it is updated, and which gate
keeps it true. It is linked from [`README.md`](../README.md).

## GitHub Actions are pinned to a commit, never a tag

A tag lives in someone else's repository and moves without a commit here: `actions/checkout@v4`
runs whatever `v4` points at when the job starts, so a force-pushed or compromised release
changes what this repository executes. Every `uses:` in `.github/workflows/**` and
`.github/actions/**` is therefore a full 40-character commit SHA, with the tag kept as a
trailing comment so the line is still readable in review:

```yaml
- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
```

Two kinds of reference are exempt, because they cannot move independently of the commit being
run: this repository's own composite actions and reusable workflows (`./.github/actions/docker`,
`./.github/workflows/pipeline.yml`).

### The gate

| Target | What it does |
|---|---|
| `make check-actions` | **Fails** on any non-local action ref that is not a full commit SHA. Part of `make ci-unit`, so a floating ref cannot merge. |
| `make actions-report` | Prints every `uses:` ref the gate reads — pin state, `file:line`, and the tag. |
| `make update-actions` | Re-resolves every pinned ref's tag to its current commit and rewrites the workflows in place. Needs `gh` (or `GITHUB_TOKEN`) and network. |

`scripts/pin_actions.py` is stdlib-only for `check` and `report`, so the gate runs on the host
exactly as CI runs it, on Linux and macOS alike. Only `update` reaches the network.

### Updating a pinned action

1. `make update-actions` — every `# vN` comment is re-resolved to the commit it now points at,
   and the SHA is rewritten. An already-current tree is byte-identical, so a second run is a
   no-op.
2. Read the diff: the tag comment is what makes it reviewable (`# v4` → `# v4` with a new SHA is
   a moved tag; `# v4` → `# v5` is a version bump and needs its release notes read).
3. `make check-actions && make check-workflows` — the pin gate and the workflow-expression gate
   (a rewritten `uses:` line must still parse).
4. Commit the result with the reason — this is the only place an Action's pin changes.

Renovate does **not** own these pins: `renovate.json` deliberately carries no
`github-actions` manager, so an unattended bump cannot move an Action without a review of this
diff. Adding that manager later is a separate decision, not an accident.

### A pin that is behind is not a broken pin

`make check-actions` fails on a *floating* ref, never on an *old* one. A pinned SHA that is
several releases behind still runs exactly the code that was reviewed, which is the property the
gate exists to protect; freshness is `make update-actions`' job, and it is a deliberate,
reviewed act.

## A gate nobody watches is not a gate

A security leg's red is only a control if something reads it. `security-scan` reds on purpose — its
`fail_on` is critical/high **with a fix** (`data/security-policy.json`, `docs/SCANS.md`), and the
floor it derives is what closes it — so the question "who consumes this run" is a design question,
not a detail.

`run-failure-reactor.yml` is the consumer: it routes any watched workflow's completed run to a repair
(a PR this repo can push) or to ONE marker-deduped `agent:implement` issue. It can only do that for a
workflow it **names**, because GitHub matches `workflow_run.workflows` against each workflow's
top-level `name:` **verbatim** and takes no wildcard. A rename therefore breaks routing silently, and
a new workflow is invisible until someone edits the list — measured on `rebase-bot.yml`, renamed by
#463, whose failures routed nowhere for a week while the roster still looked complete (#349).

`make check-workflows` holds the invariant (issue #349). It fails when a roster name is no workflow's
`name:`, when a workflow's completion is routed nowhere, when a roster names the reactor itself (a
self-trigger loop), or when an entry in `tests/fixtures/workflow-run-exemptions.json` has no `reason`
or names no workflow (stale). A workflow whose red is *deliberately* a work item is exempted there
with that reason written down — today exactly one is: `security-scan`, whose findings
`make security-issues` files and `security-bot` repairs (`docs/SCANS.md`). Route B would file a
second, head-sha-scoped issue per push to `main`, which is why the exemption exists instead of a
citation in the roster.

So a security change owes two things: a new or renamed security workflow passes
`make check-workflows` (it is watched by name), and a run that is meant to red carries either a
consumer or a `reason` in the exemption file. Adding the workflow without either is how a control
becomes a log nobody reads.

**The gate itself is a gated condition, not the status of any one run** (issue #1285). The daily
scan's *absence* — `disabled_manually`, or active but with no run within the daily cadence — is its
own control: `make all-pipelines-sweep` renders a down security-scan as `ADMISSION GATE DOWN` /
`ADMISSION GATE STALE` and fails the sweep, so the board cannot read a silently-silent scanner as
"scanned clean". A merged fix on `main` is not a clean scan; only a run id at a named sha is, and
this guard makes *not having one* visible.

**The observatory has to prove it is still watching** (issue #1291). The all-pipelines sweep is
itself a pipeline, and a gate nobody runs is not a gate — so a stopped weekly sweep reads as clean
wallpaper exactly the way a stopped daily scan used to. `make all-pipelines-sweep` now reads the
sweep's own previous run: when it is older than the weekly cadence (`ADMISSION_GATE_MAX_AGE_HOURS`
for the daily scan; its own `SWEEP_GATE_MAX_AGE_HOURS` window for the weekly sweep), the report
renders `SWEEP UNSEEN` and FAILS the sweep. A sweep whose Saturday cron silently stopped is as
visible as a scan that did — freshness is a property of the watcher every bit as much as of the
thing watched.

# Attributing a red before dispatching: read the log, then test the artifact live

A lane (or a tick, or an earlier pass of your own) says a PR is red "because of X". X is a
hypothesis until you read the failing test's own output. Dispatching on an unread attribution
sends a lane to fix the wrong file and burns a whole run.

## Order of evidence

1. Expand the matrix to the failing cell, then read that job's log — the test names its own
   blocker verbatim (a path, a tag, a version, a URL):

   ```bash
   gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '[.jobs[]|select(.conclusion=="failure")|{id,name}]'
   gh run view <run> --log --job <job-id> | grep -E 'not published|404|Failed|FAILED|timeout' | head -20
   ```

2. If the log names an **external object** (container tag, package, release asset, model repo,
   published manifest), test that object live at the exact coordinates the log printed — never
   infer its absence from the red, and never infer its presence from the PR being merged:

   ```bash
   docker manifest inspect ghcr.io/<org>/<image>:<pin>-<arch> >/dev/null && echo present || echo MISSING
   gh api /orgs/<org>/packages/container/<image>/versions >/dev/null || echo no-package
   ```

   Two of these probes are **no-verdict**, not evidence: an authenticated manifest HEAD
   (`Authorization: Bearer $(gh auth token)`) returns 403 for present AND absent tags, and
   `gh api repos/<o>/<r>/packages/container/<image>` 404s while the package plainly exists. When
   docker is unavailable, the registry's tag LIST is the authority — anonymous pull token +
   `tags/list`, assert the pin prefix across all tags (`references/engine-publish-gap.md`).

3. If the object belongs to a **sibling PR already merged into main**, the question is whether
   the producing workflow ever ran at that merged pin. Resolve the workflow id first — workflow
   *display names* carry a description suffix (`"engine-build — builds and verifies EVERY engine…"`),
   so `gh run list --workflow=engine-build` fails with "could not find any workflows named":

   ```bash
   gh api repos/<o>/<r>/actions/workflows --jq '[.workflows[]|select(.name|startswith("engine-build"))][0].id'
   gh api "repos/<o>/<r>/actions/workflows/<id>/runs?per_page=15" \
     --jq '.workflow_runs[]|"\(.created_at) \(.head_sha[0:7]) \(.status)/\(.conclusion//"-") run=\(.id)"'
   ```

   No run at the merged sha (or only runs that ended `cancelled`) is the answer: the artifact was
   never produced.

## Cancelled post-merge runs drop artifacts, and that reds every dependent gate

`conclusion=cancelled` on a post-merge run is not a verdict — and where that run was the one meant
**to publish** (image push, release upload, generated-doc publish), the cancel drops the artifact
itself. The merged pin then sits in main with no published object, and any later PR whose test
asserts "every committed pin is published" reds on *other people's* pins, 120s of polling included.

Never report such a red as content of the PR under test, never rebase it, and never send the author
lane to "fix" it. Name the mechanism on the PR board and route the *publish* to the producing lane:

- the scope is publish-only at the committed pin (`push=true` for the producer, arch limited to what
  the gate needs), with an explicit "no pin changes, no matrix edits, no branch work";
- require the report to name the run id(s) **and** the manifests read back visible on the registry
  after — a green build run is not a published tag until you can inspect it;
- hold the dependent PR untouched: its own deferred tag is expected to be absent until its own
  publish runs, so only the *already-merged* siblings' absences are defects.

## Who pushed a stray commit — shared identity is not attribution

Every lane usually pushes under the same allowlisted bot account, so `author`/`committer` on a stray
commit names the fleet, not a lane. An automated sweep that reports "Incident: lane X force-pushed
<sha>" has inferred from branch history, not evidence — while git metadata can only date the push.

Settle it with the lane, not the metadata: a first-hand confession on the record (naming the mechanics
— stale base, wrong ref fetched, lease) outranks the sweep's inference. Accept it, post one reconciliation
comment on the board quoting the confession, the commit's committer timestamp and the superseding head,
and state explicitly that no stand-down is owed by the accused lane. A misattributed incident left
standing is a board record against an innocent lane, and the next pass will re-dispatch it.

## Record the systemic finding, do not just unblock

One missing artifact is a dispatch; a class where merged pins can lose their publish to a cascade
cancel is a coverage gap in the registry-liveness / publish-order gate. After unblocking, check
whether the workflow whose job is "a committed pin whose manifest is missing must be named to the
board" actually fired — if it did not, that is an audit finding for the CI lane, stated with the
sha, the workflow run list and the 404s you measured.

---
name: github-workflow-admission
description: "Use when adding a GitHub Actions workflow to a gated repo."
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, actions, ci, workflow-hygiene]
    related_skills: [github, pr-landing-on-moving-master, github-issue-tree]
---

# Get a new workflow past the repository's own guards

## When to Use

Use when adding a new `.github/workflows/*.yml` (or materially changing one) in a repository whose
unit suite tests workflow hygiene — cron slots, concurrency groups, the shared guard step, secret
redaction rosters, dispatch forms, pinned Actions. Also use when a workflow you just added fails the
unit suite on rules nobody wrote in the contributing guide.

A mature repo does not just run workflows, it *tests* them: cron slots, concurrency, the shared
guard step, the credential roster, dispatch forms, pinned actions. Those tests live in the unit
suite, so the first full run after you add a workflow fails on hygiene you never considered — five
or six failures in one go, each a small edit. Read the guard tests BEFORE drafting, and run them
before the full suite.

## Procedure

1. **Find the guards first.**
   ```bash
   grep -rln "workflows" tests/ | xargs grep -ln "cron\|concurrency\|guard\|SECRET\|workflow_dispatch"
   ```
   Read each hit's docstring: they state the rule and the incident that produced it. That docstring
   is the spec you are coding against.
2. **Draft the workflow** from an existing sibling (copy its guard step, its `concurrency` shape, its
   permission block), not from a blank file.
3. **Run the guard tests only** — they take seconds:
   ```bash
   make test-image            # once per session: pull the test image
   docker run --rm -v "$PWD":/repo -w /repo llgenie/test:latest \
     python -m pytest tests/test_<guard files> -q -p no:cacheprovider
   ```
4. Fix, then run the guards for the generated docs (`check-dispatch-forms`, `check-docs`,
   `check-wiring`) — they fail on the table/targets your workflow adds.
5. Only then run the whole suite, in the background, and never claim green before it exits:
   `(make test-unit > /tmp/unit.log 2>&1; echo EXIT=$? >> /tmp/unit.log)` with notify on complete.

## The hygiene rules that bite (each is a mechanism, not a style)

- **The CI-leg gate-classification contract**: a repo that tests "every `ci-*` gate is FAST_GATES or DEFERRED-with-a-reason" refuses a check you wire into a CI leg unless you classify it. A new gate wired into a job without adding it to one of those sets fails the contract — the fast-suite subset may not even load the checker that crosses them, so the failure surfaces only in the FULL suite. When you wire a new gate into a CI job, add it to `DEFERRED` (with the reason it is re-checked elsewhere) or to `FAST_GATES` consciously, and run the whole unit suite before claiming green — the wiring is only proven by the run that actually crosses it.
- **Cron slot**: no two scheduled workflows may own the same `(minute, weekday)`; many repos also
  require an ODD minute. Compute the free minutes from the existing files instead of guessing:
  expand each `cron:` to its minutes and pick one nobody owns.
- **Concurrency**: every scheduled workflow declares its OWN static group with
  `cancel-in-progress: false`. A bot that cancels an in-progress run kills an agent leg mid-job.
- **The guard step is a literal**: the actor/owner/collaborator check is compared byte-for-byte
  across workflows (`name` + `env` + `run`). Copy it verbatim; do not improve its wording.
- **Credential roster**: a workflow that reads `secrets.X` must add `X` to the repo's redaction /
  secret list, or the redaction test fails and a printed value would go unmasked. `secrets.A ||
  github.token` still counts as reading `A`.
- **Dispatch form**: `name: <identifier> — <what the run does>`, every `workflow_dispatch` input needs
  a `description` plus a `default` (or `required: true`), and the `# Trigger surface: / # Flow: /
  # Never:` header block. The generated dispatch table in the docs must be regenerated from the
  generator, never hand-edited.
- **Pinned actions**: every third-party `uses:` is a full 40-hex commit SHA with `# vN` kept as a
  comment; `./…` local refs are exempt. A new workflow written with `@v4` fails the pin gate.
- **A pinned SHA can go dead, and a running tag is not a safe substitute.** A `uses:`/ SHA that
  upstream force-pushed or GC'd stops resolving — GitHub fails the run at the action-resolve step in
  seconds ("Unable to resolve action … unable to find version <sha>"), before any job body runs,
  which makes a whole gate look broken from an unrelated pin change. When that happens, verifying the
  replacement ref BEFORE the push, not after: `git ls-remote https://github.com/<owner>/<action>
  refs/tags/vN*` — the CURRENT running tag may still name the dead sha (a tag pointing at the
  GC'd object is the smoking gun), so re-pinning `@vN` repeats the exact failure. Pin instead to a
  tag's served commit (a version tag whose `ls-remote` output you confirmed resolves and that the
  GH API returns 200 for), keep the same minor line, and grep the whole tree for every occurrence
  of the dead sha — a fix that touches only the one workflow leaves an identical dead pin in a
  sibling file that fails next. This class of change sets a CI-red gate back green, so also confirm
  the gate's deciding run completes on the new head before arming auto-merge (rule: arm when the
  gate PROVES green, not when the pin "should" work).
- **Producer identity**: a script that commits must set the allowlisted identity QUOTED —
  `git -c 'user.name="Asimov Agent"'` — because the author guard parses `user.name=<value>` and an
  unquoted name with a space is read as its first word.

## Choosing the tool the job runs

- **Local-first.** Prefer the tool that needs no account, no token, and no third-party service to
  receive the analysis — a package/OS scanner plus an SBOM generator plus a matcher plus SAST covers
  "is anything in this tree known-vulnerable" with data the runner downloads itself. A scanner behind
  a repository secret has to earn its place by covering something the local set cannot.
- **Drop a redundant SaaS tool outright; do not ship it as "optional".** An opt-in variant still
  keeps a paid dependency and a credential the repo must hold, and an unset token turns every run into
  a "skipped" line that reads like coverage. Removing the image, the dispatch option, the env entry
  and the secret-roster line together is the honest change.
- **Pin the rule/config source explicitly.** `--config auto`-style modes can require telemetry (and
  refuse to run with metrics off) and pick different rules per run; name a specific pack or version
  so the result is reproducible and sends nothing.
- **A default job must run on a fork PR and on a bare runner with no secrets set.** If it cannot, it
  is not a default — make it a deliberate dispatch with a loud skip when its prerequisite is absent.

## Running a containerized scanner/CLI against the checkout

- **`--user $(id -u):$(id -g)` is mandatory** when the container writes into the mounted repo. The
  image's own non-root `USER` cannot write the runner's checkout (`failed to create output file: …
  permission denied`) and otherwise leaves root-owned files behind.
- **`docker run <image> <binary> …` goes through the image ENTRYPOINT.** To use a second binary that
  the image ships (e.g. `syft` inside a `grype` image), pass `--entrypoint syft`; passing `syft` as an
  argument turns it into a positional and the CLI refuses with `accepts at most 1 arg(s), received 2`.
- **An image published only on `push` to the default branch does not exist for a PR run.** Resolve by
  pull-else-build: try `docker image inspect`, then `docker pull`, and when both fail BUILD the same
  Dockerfile and tag it with the same immutable ref — same content, one implementation — and log
  which path was taken. A build failure must fail the run; never skip the scan silently.
- **An `if: always()` SARIF/artifact step cascades into a second confusing error** when the scan died
  early. Gate it: `if: always() && hashFiles('reports/x.sarif') != ''`.

## Pitfalls

- A `sudo` inside a `background=true` subshell has no tty and fails after the run — do the
  root-owned-`__pycache__` cleanup in a foreground call, not at the end of the background command.
- A policy that fails a PR on pre-existing findings reds every PR in the repo. Make the pull_request
  mode report-only (empty severity set) and enforce the policy on the scheduled/manual run; keep the
  severity sets in a data file so the mode is visible and gated.
- A gate that flags "a finding/artifact that did not run" must be loud (report + non-zero), never a
  silent pass: a skipped scanner or an unparseable report is not a clean result.
- Copy the generated docs table by calling the generator's own `table()` and splicing it between the
  markers — a hand-retyped table differs by one cell and the check fails again.
- The unit suite runs in a container mounted on the LIVE checkout, so a commit or edit made while it
  runs is read mid-flight and its failures can be artifacts of a half-updated tree. Before believing
  a failure, check `git log`/`git status` for changes during the run and re-run the affected files
  on the settled tree.

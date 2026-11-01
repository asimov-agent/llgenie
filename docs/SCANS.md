# Scans — Trivy, Syft, Grype and Semgrep from their pinned images

The scan pipeline is `.github/workflows/security-scan.yml`; every scanner it runs comes from
[`docs/SCANNERS.md`](SCANNERS.md)'s immutable image, and the one place a scanner is invoked is
`scripts/security_scan.py`. There is no second code path: the workflow, a developer and CI call the
same `make` targets.

## Triggers — its own daily pipeline, never a PR or push check

| Event | When | Failure policy |
|---|---|---|
| `schedule` | daily 04:05 UTC | `full` mode — `fail_on` (critical + high, with a fix) |
| `workflow_dispatch` | owner, repository bot, collaborator with write | the `enforce` input, default `full` |

**There is no `pull_request` trigger and no `push` trigger, on purpose (issue #738).** A scan answers
"is an upstream package old today", and `main` CI answers "does this change work"; putting the first
on every PR and every push made a pre-existing advisory red the pipeline forever. Measured: run
40525155122 (a push) failed on `certifi`, `filelock` and `urllib3` — transitive pins nothing in the
repository bumped. `make check-security-scan` now **fails** when either trigger is added back, and it
also fails when `enforce_events` in `data/security-policy.json` names `push` or `pull_request`.

**The scan also looks for a committed credential** (issue #1283). The same digest-pinned trivy image
is asked for its `secret` ruleset too (`--scanners vuln,secret`), so a `ghp_`/`sk-…`/cloud key in a
trackable file is a first-class finding: it flows through `security-verdict` and `security-issues`,
appears in the uploaded SARIF (`category: trivy`), and — because a committed secret is always
actionable (remove + rotate, never "wait for a patched version") — it blocks the daily run even
though it has no fixed version, while `fail_on` still gates a `medium`/`unknown` secret to recorded,
not red.

The manual form asks two things: `tools` (`all` or one scanner) and `enforce` (`full`, or `report` to
run the whole sweep without gating). The `guard` job runs **before any scanner** and allows the owner,
`github-actions[bot]` on a same-repo head, and any collaborator with `admin`/`maintain`/`write`;
anyone else is refused.

## Which events may gate, and what a report-only run does

The set of events that may fail the run is **data**, never a literal in a workflow step:

```json
{"fail_on": ["critical", "high"], "pr_fail_on": [], "enforce_events": ["schedule", "workflow_dispatch"],
 "require_fix": true, "issue_severities": ["critical", "high"]}
```

`enforce_events` names the ONLY events that can gate. Any other event — and an explicit `ENFORCE=pr`
dispatch — is **report-only**: every finding is counted, printed, uploaded as SARIF and filed as an
issue, and the run exits 0. `pr_fail_on` is the narrower set such a run would use; it is empty on
purpose.

`require_fix: true` means an advisory with no fixed version is **recorded, never blocking** — it is
work nobody can do today, and #716 decides which recorded findings become issues.

## Where the scanner image comes from

The run uses the ref `containers/scanners/digests.json` names. It is **pulled** when it is published.
A `pull_request` run before the first publish — and any run whose token cannot read the packages —
does not skip the scan: the **same Dockerfile** the publish job builds (digest-pinned base, exact
versions) is built locally and tagged with the ref the run asked for, and the log says which path was
taken. A build that fails fails the run, loudly; there is no third path and no silent skip.

Every scanner runs as the **invoking user** (`docker run --user <uid>:<gid>`): the mounted checkout
belongs to the runner, so without it trivy cannot create its report (`permission denied`) and the run
would leave root-owned files in the tree (issue #433).

## Outputs

- **CycloneDX SBOM** — `security-reports/sbom.cdx.json`, written by Syft from the Grype image;
  uploaded as the `security-reports` artifact (30-day retention) together with every scanner report.
- **SARIF** — `security-reports/trivy.sarif`, uploaded to the Security tab with
  `github/codeql-action/upload-sarif` (pinned by SHA), category `trivy`.
- **Reports** — `security-reports/sbom.cdx.json`, `trivy.json`, `grype.json`, `semgrep.json`.
- **No scanner takes a secret.** Trivy, Syft, Grype and Semgrep run from their pinned images, so
  no scan is ever skipped for a missing credential.

## Targets

| Target | What it does |
|---|---|
| `make sbom` | Syft → `security-reports/sbom.cdx.json` |
| `make security-scan TOOL=<id>` | one scanner from its pinned image (Grype needs `make sbom` first) |
| `make security-scan-all` | Syft SBOM, then Trivy, Grype, Semgrep |
| `make security-verdict MODE=full\|pr` | apply the policy to the reports; the run's exit code |
| `make check-security-scan` | **The gate** (inside `make ci-unit`): empty/unknown policy severities, `pr_fail_on ⊄ fail_on`, or a scanner missing from `digests.json` fails |

## Findings become tagged issues

`make security-issues` (after the verdict, on a `push`, a `schedule` run and a manual dispatch —
never on a `pull_request`, whose findings belong to the PR) turns the reports into GitHub issues:

- **one issue per (advisory, package)**, keyed by an HTML marker in the body
  (`<!-- security-finding: trivy:CVE-…:numpy -->`), so a re-scan **updates** the same issue and
  never opens a duplicate;
- **labels**: `security`, `vulnerability`, `severity:critical` / `severity:high`,
  `component:python` / `component:container` / `component:code`, and `auto-fixable` when the
  scanner names a fixed version — every label is created (with colour and description) on first use;
- **body**: advisory id and scanner, affected package, current → fixed, severity, the run link,
  the suggested action, and a `Not covered` section;
- **clearing**: an advisory the scanner no longer reports is commented with the run that cleared it
  and closed; a closure that `gh` refuses (a remediation PR still references it) is a warning, never
  a crash.

`make security-issues-plan` prints the same create/update/clear plan and mutates nothing.

| Target | What it does |
|---|---|
| `make security-issues-plan` | print the plan (no GitHub write) |
| `make security-issues SLUG=owner/name RUN_URL=<link>` | create/update/close through `gh` |
| `make check-security-issues` | **The gate** (inside `make ci-unit`): `issue_severities` empty or not a subset of `fail_on`, a missing label, or a marker that does not round-trip fails |

## The remediation bot

`.github/workflows/security-bot.yml` runs `make security-bot`, which is `scripts/security_bot.py`:

1. **select** the oldest open issue carrying `security` + `vulnerability` + `auto-fixable`;
2. **parse** the package and `current -> fixed` out of the body the issuer wrote (#716) — a body
   without those lines is refused, never guessed;
3. **edit the one line that owns the pin** (`tools/requirements.in` / `requirements-dev.in`). A
   compiled `requirements*.txt` is never an edit target — it is regenerated;
4. **run the fast gates** (`make lint check-wiring check-docs check-security-scan`);
5. **push a branch and open ONE PR** whose body carries `Issue: / Fix: / Benefit: / Technical:` and
   `closes #<issue>`.

**Green or nothing:** when a gate is red the bot reverts the edit, comments the real output on the
issue, and opens no PR. It never merges, never pushes to `main`, never force-pushes.

It **refuses** a finding it cannot place — a `component:container` advisory (a base-image or
scanner bump, which is a reviewed change) or a package pinned nowhere it can see — and says so on
the issue instead of guessing.

| Target | What it does |
|---|---|
| `make security-bot-pick` | print the one issue the run would take |
| `make security-bot DRY=1` | print the edit, push nothing |
| `make security-bot` | apply, run the gates, push, open the PR |
| `make check-security-bot` | **The gate** (inside `make ci-unit`): the select labels must exist in the issuer's roster and no compiled file may be an edit target |

## The scan fixes what it reports: the floor, regenerated into the pins

A red scan that nobody can act on is noise, so the daily run closes its own loop (issue #738):

1. **Derive the floor.** `scripts/security_bumps.py` reads the reports and, per package, takes the
   lowest fixed version that clears **every** advisory reported for it (the maximum of the
   minimums). Only a finding with a fixed version becomes a floor, and the value is always the
   scanner's own `fixed` — nothing is invented.
2. **Write it once.** `tools/security-floors.in` is a pip-compile constraint file, e.g.
   `urllib3>=2.8.0   # trivy CVE-2026-97687: 2.7.0 -> 2.8.0`. Both `tools/requirements.in` and
   `tools/requirements-dev.in` include it with `-c security-floors.in`, so the compiled files
   respect it without a second source of truth.
3. **Regenerate, never hand-edit.** The daily run calls `make -C tools generate-requirements` and
   `generate-requirements-dev` — the ONE generator (AGENTS.md). A compiled `requirements*.txt` is
   never an edit target.
4. **One PR that closes what it fixes.** The change lands on `fix/security-floors` with a body
   carrying `Issue: / Fix: / Benefit: / Technical:` and `closes #<n>` for every tagged issue (#716)
   it fixes. An unsatisfied floor after the regeneration, or a red fast gate, reverts the file, opens
   **no** PR and exits non-zero.

Renovate (`docs/RENOVATE.md`, #718) keeps the same pins moving *forward* between scans; the floor is
the minimum an advisory *requires*. What neither can place — a base digest with no newer upstream
digest, an action SHA, a floor the resolver refuses — is #739.

| Target | What it does |
|---|---|
| `make security-bumps-plan` | print the floor, the pins it would move, and the issues the PR would close (no write) |
| `make security-bumps DRY=1` | same, and nothing regenerated or pushed |
| `make security-bumps` | write the floor, regenerate both compiled files, gate, push `fix/security-floors`, open/update the PR |
| `make check-security-bumps` | **The gate** (inside `make ci-unit`): a floor line with no advisory, a compiled pin below its floor, or a missing `-c security-floors.in` fails |

## Reading a failure

`make security-verdict` prints every blocking finding as
`<source>: <advisory> <package> <current> -> <fixed> (<severity>)`. That line is exactly what
`make security-issues` (#716) turns into a tagged issue with the `security`, `vulnerability`,
`severity:*`, `component:*` and `auto-fixable` labels.

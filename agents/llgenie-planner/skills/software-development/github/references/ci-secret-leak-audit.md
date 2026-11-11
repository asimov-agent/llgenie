# CI Secret-Leak Audit (logs + artifacts + runner restrictions)

Answer "have any secret VALUES leaked into GitHub Actions logs or artifacts, and
are the bots actually restricted?" for a repo. Scan EVERYTHING, not a sample —
GitHub masks only the exact registered values, so a transformed spelling
(URL-encoded, base64, a slice) sails past the mask and into a public log.

## Procedure

1. **Enumerate every run** (paginate; `--limit` caps at 100/page):
   ```bash
   gh run list --repo <o>/<r> --limit 1000 --page 1 \
     --json databaseId,workflowName,createdAt,conclusion,headSha \
     --jq '.[] | [.databaseId,.workflowName,.createdAt,.conclusion,.headSha[0:7]] | @tsv'
   ```
2. **Download every run log** into a scratch dir:
   ```bash
   gh api repos/<o>/<r>/actions/runs/<ID>/logs > z/<ID>.zip   # then unzip each
   ```
   A 404 here means the log is gone (deleted/expired) — record it as UNCHECKED,
   never as clean. `gh run list` may not return every run; cross-check the count
   against the API's `total_count`.
3. **Download every artifact** (public repo: downloadable by anyone logged in):
   ```bash
   gh api repos/<o>/<r>/actions/artifacts --paginate --jq '.artifacts[] | [.id,.name,.expired] | @tsv'
   gh api repos/<o>/<r>/actions/artifacts/<ID>/zip > a/<ID>.zip
   ```
4. **Scan** with `scripts/scan-ci-secrets.py` (credential shapes + literal values
   of every secret present in the local env, in raw/base64/URL-encoded/prefix
   spellings).
5. **Verify the restrictions**, not just the absence of leaks:
   - runner identity: `gh api repos/<o>/<r>/actions/runners` — self-hosted
     runners persist state between runs; hosted ones are fresh VMs.
   - `permissions:` at the TOP of each workflow (so the repo default write token
     never applies) and the guard job as the FIRST job of every bot pipeline.
   - retention: `gh api repos/<o>/<r>/actions/permissions/artifact-and-log-retention`.
   - interaction limit (who can open PRs/issues/comment) and its expiry.
   - fork PR handling: no secrets + approval required for external contributors.
6. **Prove the redaction actually ran in CI** since the fix commit — a run whose
   agent step was SKIPPED (`implement skipped`, `pick skipped`) proves nothing.
   Check the run's job conclusions and that the guarded step executed, then
   trigger one real run and rescan its log.

## Pitfalls

- **Only secrets present in the local shell can be searched literally.** The
  others are covered by shape alone. Report explicitly which values were checked
  literally and which only by shape — a shape-only scan is weaker and the report
  must say so.
- **`dockerbuild` artifacts are gzip, not zip** — `zcat`/`gzip -d`, never
  `unzip`. A `zipfile.ZipFile()` open fails on them; that is a format mismatch,
  not a corrupt artifact.
- **An `sk-` shape match is often a signed blob URL, not a secret.** A
  `.../data?Expires=<ts>&Signature=<base64>` string matches the `sk-` shape but
  is a time-limited download URL. Read the surrounding context and check the
  `Expires` timestamp before flagging it.
- **Credential-shape matches in test/patch files are usually variable NAMES, not
  values** (`NOUS_API_KEY="NOUS_PORTAL_API_TOKEN"` in a fixture). Check the
  context: a name in an assignment is a reference, a value is a leak.
- **A token-shaped URL (`https://x-access-token:<var>@git...`) in a log is a false
  positive when it is a variable NAME passed via `env:`.** The masked VALUE shows
  on its own line (`BUMP_TOKEN: ***`) and the URL holds the variable reference,
  not a literal. The distinction lives in the SOURCE, so git-grep the workflow
  before flagging: a secret read as `${VAR}` from an `env:` block is masked by
  GitHub; a `${{ secrets.X }}` interpolated INSIDE a `run:` block is rendered as a
  literal value into the script and echoed when the script runs — the shape a
  workflow comment calls "a value in a log waiting to happen". Only the second is
  a leak.
- **An empty secret line on a fork `pull_request` run is WITHHELD, not masked and
  not a leak.** GitHub does not deliver secrets to fork PR runs, so `HF_TOKEN:` /
  `KEY:` blank there is expected. Verify masking on a `push`-to-`main` (or other
  same-repo event) run, where the secret actually reaches the runner and MUST be
  `***` — never conclude "no masking" from an empty value on a fork run, and never
  report an empty fork-secret line as evidence of a problem.
- **`##[debug]` lines mean debug logging was enabled** — that is the one mode
  that dumps every env var. Grep for it; its absence is part of a clean result.
- **A redaction wrapper that prints only a bounded tail is not enough** — the
  raw stream must be captured to a file and only the scrubbed tail printed, and
  only the SCRUBBED file uploaded as an artifact. Verify the artifact path is
  the scrubbed log, not the raw one.
- **A run that skipped its agent step is not evidence the redaction works.**
  `implement skipped` / `pick skipped` runs exercise nothing. Only a run that
  actually executed the guarded step counts.

## Report shape

Lead with the verdict (clean / leaked / unchecked), then: what was scanned and
how many lines, which values were checked literally vs by shape, the false
positives you ruled out and why, the runs you could NOT download, the runner/
permission/retention facts, and what has NOT yet been proven live. Never claim
"no secrets leaked" for runs you could not download.

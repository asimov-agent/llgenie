# Building secret-masking into bot/agent workflows (prevention)

How to make a CI bot/agent workflow that reads secret env vars never leak their
VALUES into logs, artifacts, or `$GITHUB_OUTPUT`. This is the build side; the
`ci-secret-leak-audit.md` reference is the audit side (scan what already ran).

## Design pattern

- **ONE list of env keys is the source of truth**, not scattered per-step `env:`
  blocks. Every leg reads the same list, so a key added once is masked and
  guarded everywhere. Derive the roster from the Makefile/workflow, not a
  hand-maintained duplicate that drifts.
- **Redact by NAME, never by value.** For each key, scrub its value in raw,
  URL-encoded, base64, and common shape spellings (a transformed spelling sails
  past GitHub's exact-value mask). Report COUNTS of redactions, never the
  values — a count proves the scrub ran; a value is the leak.
- **A seam to force-inject a key into the agent's shell** (e.g. an
  `_HERMES_FORCE_<NAME>` env var) so the redaction is exercised with a real
  value in a hermetic test. Without a real value the scrub path is dead code.
- **Guard before the image pull, fail loudly.** A `require_env` step that exits
  non-zero on a missing OR empty key, placed as the FIRST recipe line of every
  leg, makes a run that would "do nothing and report green" impossible. A
  container that has the key but whose agent shell reads it EMPTY is the
  silent-failure shape to prevent.
- **Step-scoped env rules.** A rule about the step that runs the agent must
  check THAT step's `env:` — a sibling step's `env:` does not satisfy it. This
  is exactly the shape of the bug where the key is set on the wrong step and
  the agent's shell reads it empty.
- **`${{ github.token }}` written inside a `run:` block is evaluated by GitHub
  and can leak.** Never put expression syntax in a `run:` block comment — a `#`
  line there is SCRIPT TEXT, not a YAML comment, and an unparseable expression
  refuses the whole workflow file (0-job run whose name is the file path).
- **Whole-stdout into `$GITHUB_OUTPUT` or into the log is a leak vector.**
  Capture the raw stream to a file, scrub it, and only publish the scrubbed
  file as the artifact / tail.

## Repository-secret lifecycle: `gh secret set` + the name-only readback

When a CI workflow is wired to consume a masked key, the secret its job reads
has to EXIST on the repo/org first (a smoke/Search leg that reads a key with no
secret defines is human-run-only — see the last pitfall below). Creating and
verifying it:

- **`gh secret set <NAME> --repo <owner>/<repo> --body <value>`.** The scope
  (`repo`, `org`, `env`) is explicit — for a repo secret the `--repo` is
  required, not inferred from cwd. For a non-interactive/agent run feed the
  value via `--body` (or stdin) so it is never exposed as a shell-history
  argument; a value beginning with `@` is treated as a file path by `gh`.
- **You can never read a secret's value back.** GitHub stores it write-only
  (the API returns `encrypted_value` as a masked string, never the plaintext).
  "Verify the secret exists" therefore means **verify by NAME**:
  `gh secret list --repo <o>/<r>` / `gh api repos/<o>/<r>/actions/secrets
  --jq '.secrets[].name'` shows the name and the `updated_at` timestamp of the
  write. A "created + verified" claim = the name appears in that listing, not
  that the value round-trips.
- **Because the value is single-shot, keep the payload you set.** If you need
  the plaintext again later (re-provision on a fresh repo, a second env), the
  owner must re-supply it — you cannot fetch it back. Guard that capture: if
  the user gives you the value in chat/OOB, set it immediately and tell them
  it is now write-only and cannot be recovered.
- **A secret's VALUE is only ever proven by a real consumption run.** Setting
  it proves the NAME exists; the scheduled/CI job that reads it and makes a
  real call is the proof the value is valid. The octet `***` masking in a log
  only proves the name resolved to SOME value — a masked value, not a working
  credential.

## Verification (a scanner that cannot catch a planted value proves nothing)

- **Self-test:** plant a known value and assert the scanner catches it; then
  remove it and assert clean. A scan that reports "no leaks" without ever
  having caught a planted value is unverified.
- **Prove the redaction ran in CI**, not just locally: a run whose agent step
  was SKIPPED exercises nothing. Check the run's job conclusions and that the
  guarded step executed, then trigger one real run and rescan its log.
- **A missing repository secret is a real gap, not a config detail.** If a
  masked key has no secret defined, the smoke test that needs it is
  human-run-only; record that decision explicitly (e.g. a host-only-wiring
  fixture) and wire the secret in as its own follow-up rather than folding it
  into the masking change.

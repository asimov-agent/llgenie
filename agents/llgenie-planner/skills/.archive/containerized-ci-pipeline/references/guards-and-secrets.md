# Contract validation, additive-only guards, and secret scanning

Topical depth for the containerized CI data pipeline. The SKILL.md body points
here; these are the rules for guarding derived/vendored data and for keeping
credentials out of a public repo.

## Contract validation: prune vs widen, and versioning

When an agent writes data that must conform to a JSON Schema contract
(`additionalProperties:false`):

- **Prune** stray/one-off extra keys via a self-correct step (fill missing
  fields AND strip undeclared top-level keys) — run it BEFORE validate, not
  after.
- **Widen** the contract only for real, recurring new keys, and update the
  tests in the same change.
- **Versioning**: additive change (new key/enum that existing records still
  satisfy) → edit the same contract file in place. Breaking change
  (removing/renaming a key, changing a type) → create `*.v2.json` and route
  old data to the old contract, new data to the new one. Never silently
  re-validate old data against a changed contract.
- **A constraint that would reject the CURRENT store is a REPORT-ONLY check,
  not a hard gate.** When the additive-only rule forbids tightening a
  free-text field into an enum (the store already holds values the enum would
  refuse), do not widen the contract to a shape the store violates and do not
  silently drop the offenders. Add a report-only validator check that prints
  the distribution and names each offender (a unit-less value as a
  misspelling, an out-of-category value as such), and let a degenerate store
  report instead of raising. The check is the visibility; a human decides
  whether to normalize the store or widen the contract. Register it in a
  stage's `--only` list like any other check (rule 6d) — report-only means
  it never fails the run, not that it never runs.
- **A marker regex must be deliberately strict — a loose one misclassifies
  prose as a declaration.** When a field carries a marker value (e.g.
  `vram_min: "CPU"` meaning "no GPU needed"), match only the bare marker
  forms (`^cpu(?:[- ]?only)?$`, case-insensitive). A sentence that merely
  mentions the concept — `"system RAM holds the expert set (32GB GPU + system
  RAM)"` — also names a GPU and must NOT be read as the marker; a loose match
  silently turns a real requirement into a false declaration. Test the prose
  value explicitly as a negative case, and keep the marker's fallback honest
  (a stated number still wins; only the bare marker is the declaration).
- A validator that parses a markdown table must read only the target column —
  parsing the whole row picks up Params/VRAM as if they were the metric and
  flags correctly-sorted tables as unsorted. Two more traps in the same cell
  parse: (1) an embedded DATE (`tps (YYYY-MM-DD)`) leaks the YEAR into the
  numbers — strip `\(\d{4}-\d{2}-\d{2}\)` BEFORE `findall`, or `max()`
  returns 2026; (2) an arbitrary `n < 1000` filter "to skip non-tps numbers"
  silently DROPS a legitimate 1000+ t/s (spec-decode 1250), so a
  correctly-sorted table reads as unsorted. The target cell holds only t/s +
  date, so take `max(nums)` over the date-stripped cell with NO upper bound.

## Additive-only guard against the PREVIOUS snapshot

For vendored/derived data (a store regenerated from an upstream source), fail
when any key, measurement, t/s or engagement counter that existed in the LAST
snapshot disappears from the new one — a sync that silently drops data is a
regression, not a cleanup. Compare against the previous snapshot, never a
schema.

- Prove it real: run the check on the OLD code (fails) and the NEW code
  (passes) against the same before/after store.
- Mirror the guard on the CONSUMER side too: a downstream repo that ingests the
  vendored store must also fail when the vendored data loses a key, so a
  lossy upstream sync is caught at the consumer's own gate, not just upstream.

## A check that is not in a stage's `--only` list is dead code

When a validator runs stages selected by a Makefile `--only` list, a new
`check_*` function that is not registered in the stage that list selects never
runs — CI stays green while the check silently does nothing. Register every new
check in the stage it belongs to AND in the `--only` list that selects it, and
add a wiring test asserting each `check_*` is reachable through a `--only`
stage.

## Secret scanning as a pre-push + first-CI-step gate

A data pipeline that writes tracked files (prompts, snapshots, fixtures,
README) can silently commit a pasted credential to a public repo. Gate it with
a real scanner, not a convention.

- **gitleaks** (MIT, single Go binary, 150+ detectors, official pinned image)
  is the FOSS pick for a BLOCKING pre-push scan. trufflehog is for live-
  credential *verification* — a network round-trip per candidate is the wrong
  shape for a pre-push block; detect-secrets is baseline-oriented with a weak
  history story.
- **`dir` mode does NOT honour `.gitignore` — a scan must run over the TRACKED
  file set, not the working tree.** gitleaks `dir /repo` walks the filesystem
  and scans gitignored files too, so a repo whose `make test-unit` leaves
  `tests/__pycache__/*.pyc` (bytecode carrying the test suites' planted
  sentinel VALUES) makes a LOCAL `make secret-scan` report two "leaks" inside
  the pyc, print the "credential shape in the working tree — rotate the key"
  remediation jargon, and exit non-zero — even though the same tree
  (`git archive HEAD | tar -x` into a temp dir, then scan THAT) is clean.
  CI stays green ONLY because a fresh runner has no cache directory. Before
  acting on a secret-scan finding: prove it with `git check-ignore -v <path>`
  (the route says `.gitignore:N:…` → the file is NOT committable) and with a
  scan of a clean `git archive` export; a finding that lives only in ignored
  paths is machinery noise, not a leaked key. Run the scan over the tracked
  set (gitleaks `dir` against a clean export, or scan specifically ignored-
  egress paths first) so an exposed value in a committable file is what trips
  the gate.
- Run it over the working tree INCLUDING staged files (`dir` mode), `--redact`,
  `--exit-code 1`, repo config; make it the FIRST step of the CI validate job
  so a planted secret turns the PR red. A history scan (`git log -p`) catches
  a value deleted later that a working-tree scan cannot see — but refuse a git
  worktree loudly rather than scanning 0 commits and reporting a fake clean.
- **Never allowlist a real value.** A widened `.gitleaks.toml` may only exempt
  documented PLACEHOLDERS and machine-generated baselines, each with a comment
  saying why it is safe; a real credential that trips a rule is a leak to
  rotate, not a config edit.

## A guard job must declare NO secret, or a refusal never protects it

The actor/triggering-actor guard is only as strong as where it runs relative
to the secrets. A guard *step* inside a job that declares secrets in a
job-level `env:` is too late: the runner materialises every job-level secret at
job start, before step one, so a refused caller was already handed the key. Two
properties to hold:

- **The guard is its own first job that declares NO secret** — put the actor
  check and the secrets in separate jobs, the work in a `needs: guard` job
  (never a bare `if: always()` on the work job, which runs on a refused guard;
  combine `always()` with `needs.guard.result == 'success'`).
- **A workflow test that greps the YAML for a guard STEP is blind to the
  secrets-in-env shape** — a guard step can exist while forbidden jobs still
  declare secrets above it. Assert instead that no step in the guard job (and
  no secret in that job's `env:`) reads a secret, and that the first
  secret-bearing step sits strictly after a `needs: guard` boundary.
- **Self-test that plants a fake credential and REQUIRES detection**
  (`make secret-scan-self-test`): assemble a well-formed FAKE key from string
  parts (so the probe file is not itself a leak), assert the scanner flags it,
  then assert a clean fixture passes. A scanner that silently does nothing
  fails this — a false green is the failure mode to guard against.
- Complements the "verify a pushed image has no baked secrets" check: that
  proves the image is clean; this proves the working tree stays clean.

## Agent-stream output is a leak channel — redact, never rely on GitHub's mask

An LLM/agent run has TWO consumption paths a tree-only scanner cannot see: the
console and the run's artifacts. When an agent's stdout is echoed to a CI log, a
secret it was handed as `-e NAME` can come back verbatim inside the agent's own
prose ("set it as `Bearer <KEY>`") — the human then posts the log to a public
issue thread. Rules that hold:

- **GitHub masks only the exact values it registered as secrets** (and often
  only for the repo that registered them). A transformed spelling — URL-encoded,
  base64, a sliced/reflowed chunk, a leading-whitespace variant — sails past the
  very mask that hides the original, and the console shows it unmasked. So
  "GitHub masked it" is not a pass; bootstrap nothing on it.
- **Gate the whole captured stream through a redactor keyed by SECRET NAME, not
  by a fixed value list**: for each secret name, search its value in every
  spelling (raw, URL-encoded, base64) plus the raw credential shapes
  (`ghp_`, `sk-`, `hf_`, `fc-`, `jev-`, `Bearer …`), keep a bounded tail, and
  fail loudly (non-zero) when the log it was told to redact is missing — a
  missing scrub output must never read as "clean". Print a marker line
  (`[scrub-log] N redaction(s)`) so a reader can tell stdout was scrubbed.
- **Make the agent run non-interactively** (a blanket `--yolo --accept-hooks`
  flag on every recipe) so a capture/scrub pipe never hangs on an interactive
  prompt and never leaks the prompt half-typed.
- **Everything after output is generated is the leak surface**: commit the
  redactor + the guard that demands it, and test the SHIPPED step (a stub `make`
  driving the real `run:` block, a live fake secret in the env) asserting zero
  leaks in console AND artifact.

## The redaction seam lives in the PUBLIC make target, and the guard reads TARGETS

Put the capture-and-redact seam in the public `make` target, not in each caller.
A workflow step, a shell script and a human all reach the agent through `make`;
repeating the redaction per caller is exactly how a caller gets missed (a
`fix_loop.sh` that pipes `make fix` through `tee` was the one that slipped).
One `define scrubbed_run` (capture to a gitignored log, print the redactor's
bounded tail, exit with the command's own status) applied to every public agent
target means a new leg cannot forget it.

- **The guard must match the TARGET names, never the literal recipe text.** A
  rule that greps for the exact wrapper string (`$(DOCKER_RUN) sh -c "…"`) is
  blind to the matrix form `make search-${{ matrix.backend }}` and to a call
  made from inside a shell script — both are how a target escapes the seam
  while the guard stays green. Assert each public target's recipe contains the
  seam, and cover the matrix step EXACTLY when every leg self-scrubs: one leg
  losing the seam must re-open the check (test both directions).
- **Refuse a gutted seam, not just a missing one.** A seam edited so it no
  longer calls the redactor silently un-covers every target that uses it — one
  edited function defeats six targets. The guard must fail when the seam's own
  body stops invoking the redactor.
- **When you change a make target's recipe, grep the test tree for the literal
  string you changed.** A test that asserts the old wrapper text (a backend
  table test asserting `$(DOCKER_RUN) sh -c …`) fails after the change; update
  it in the same change (rule 6b) or the suite goes red on a shard you did not
  run.

## The run-log audit — verify the pipeline, not the tree

All the repo-side scans read the working tree; a value that reaches a run LOG
never touches the tree, so it is invisible to them. When a change alters ANY way
a value can reach a log or artifact, VERIFY in the real pipeline before calling
it done:

- Pull the affected runs' logs (`gh run view <id> --log`, worktree + dispatch
  legs across every bot: implementer, reviewer, qa-validate, refresh, fix) and
download their artifacts. Scan for (a) raw credential shapes, (b)
`NAME=value` lines whose value is NOT GitHub's `***`, (c) URL-embedded
`?key=`/`token=` values, (d) high-entropy tokens (28+ chars, letters+digits),
excluding digests/UUIDs/branch names/URLs.
- **Classify hits before declaring a leak**: a placeholder the agent wrote in
  its own instructions (`<key>`, `***…`, `fc-xxx`) is NOT a leak — but it is the
  latent risk, because a future run can paste the real value exactly there.
  A real value, or a `NAME=<value>` the console did not mask, IS a leak even if
  surrounded by masked text.
- **Every `***` in a GH Actions log falls into a small set of benign categories —
  classify ALL of them before declaring a leak.** A masked occurrence in OUR
  output (not one of the categories below) means a value DID reach the log
  stream and GitHub saved it, so the taxonomy is what separates "no value
  readable" from "a value flowed through". The benign set:
  1. `NAME: ***` in a step's `env:` listing — GitHub's own mask of the secrets
     it injects; not our output.
  2. `token: ***` / `password: ***` / `github-token: ***` and
     `git config --local http.…/.extraheader AUTHORIZATION: basic ***` —
     `actions/checkout`'s own command echo of the repo token it configures as a
     git credential. This is the ONE credential that appears in every checkout
     job, always masked; recognize it as benign and standard for every Actions
     job (not a repo defect, nothing to rotate) instead of re-deriving it.
  3. `make: *** Error N` / `make[1]: ***` — make's error prefix, not a secret.
  4. The repo's own literal `***` placeholders inside prompt text (e.g.
     `Authorization: Bearer ***` written into a Makefile `-z` prompt) and the
     agent quoting them back — static text, not a mask. Anchor the classifier
     on the full literal, not a bare `***` match, or the recipe echo of the
     prompt counts as "unexplained".
  Only an occurrence fitting NONE of these is a real exposure signal.
- **Answer the two claims separately**: "no token value was ever readable"
  (true when every `***` is benign) and "a credential passed through the log
  stream masked" (true for the checkout token in every run) are different
  statements — report both, and name the one credential that did flow (the
  checkout repo token) rather than a bare "all clear".
- **ROTATE a value found in a log or artifact** — in the provider AND in the
  repo secret. Masking/redacting the copy is not a fix for one already emitted;
  tell the user the value is exposed and that a rotation is required. "No key
  needs rotating" is a finding you state only after the audit shows zero real
  values.
- An uploaded ARTIFACT is a leak channel equal to the console; a run that uploads
  its own report/patch/log must upload the REDACTED copy, never the raw stream.
- **Scan the WHOLE population of the risk workflow, not a sample.** The risk
  population is every run of the workflow whose prompt pushes the agent toward a
  key-bearing header (the key is in its env AND the prompt tells it to build
  `Authorization: Bearer <key>`). Enumerate all runs
  (`gh api repos/<o>/<r>/actions/workflows/<wf>.yml/runs?per_page=100`), scan
  each, and report the count scanned. A run with no retrievable log (outside the
  90-day retention) is a permanent blind spot — name it rather than folding it
  into "clean".
- **Decide whether a hit is safe to print by charset, not by eyeball.** A value
  is placeholder (safe to quote verbatim) only when its character set is
  placeholder furniture (`fc-.<>…`'\"[]()/`) or it starts with
  `<`/`` ` ``/`$`/`http`; otherwise withhold it and report only its length. A
  real key matches a shape regex (`fc-[A-Za-z0-9]{16,}`, `gh[pousr]_…`, `sk-…`,
  `hf_…`) — count those separately; zero shape matches is the decisive "no key"
  test, stronger than reading the text.
- **Never abbreviate a placeholder into a shape that reads like a truncated
  secret.** Reporting `fc-...` as `fc-xxx` makes a clean log look like a masked
  key and sends the user hunting for a rotation that is not needed. Quote the
  literal or say "placeholder text (no key entropy)".
- **Your own tool's display masks key-shaped text — never read a mask as the
  file's content.** The terminal/UI output filter replaces `Bearer <word>` and
  key-name-shaped strings with `***` in what it shows you, so a Makefile that
  actually contains `Bearer $${FI...KEY}` (an elided variable name) renders as
  `Bearer ***` while `grep -c '\*\*\*'` on the file returns 0. Before you
  assert what a file or log contains in a security claim, verify with
  unmaskable measurements — the hex of the segment, its character-class
  counts, the LENGTH of the span, or a match COUNT (a count cannot be masked)
  — and quote the verified bytes, not the displayed ones. A misread mask
  repeated to the user is a false finding you then have to retract.
- **When aggregating per-run maxima, take the max — never the sum — and label
  the aggregate by the operation actually performed.** Summing per-run "longest
  value" lengths and printing the total under a `longest` label is a false alarm
  (a 147 that was really 11). Verify the aggregate label matches the operation
  before reporting it.

When the audit finds nothing, report the numbers (lines pulled, shapes found,
longest matched string) rather than a bare "all clear" — the numbers are what
make "no leak" verifiable rather than asserted.

## A prompt that names a credential must name a variable that exists — and a missing key must fail loudly

- **Verify the credential NAME a prompt references actually exists in the
  environment.** A prompt that tells the agent to build `Authorization: Bearer
  $${FI...KEY}` (a truncated/elided variable name) while the real env var is
  `FIRECRAWL_API_KEY` is a silent defect: the agent cannot authenticate, burns
  turns hunting for the key, and writes placeholder instructions into the
  public log — the exact behavior a secret audit then has to explain. Grep the
  prompt for the exact name and confirm it is exported into the container.
- **A secret row that exists but is EMPTY is the same failure as a missing
  one.** The workflow passes `NAME: ${{ secrets.X }}` and docker forwards
  `-e NAME`, yet the agent measures `${#NAME}` = 0 and gets HTTP 401 — the
  wiring is correct, the secret's VALUE is empty. Check the effect (a length
  probe in the container), not just the wiring.
- **A leg whose credential is missing must FAIL LOUDLY, not degrade.** A
  keyless leg that quietly runs a fallback path and lets the agent explain
  itself in prose reports success while doing something different — the same
  class as a pre-flight that prints SKIP and exits 0. A missing/empty key
  should be a red check naming the variable, never a green run with a prose
  apology.

## A secret that reaches the container can still be invisible to the agent's shell

A credential can be present in the container (GitHub's env listing shows
`NAME: ***`, the value is exported) yet ABSENT from every command the agent
runs — because Hermes strips it. Provider/tool credential names
(`FIRECRAWL_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) are on Hermes's
credential blocklist (`tools/environments/local_env_policy.py`), so they are
removed from the agent's command environment by design, and `env_passthrough`
can NEVER re-allow a blocklisted name. This is the root cause of a bot that
reports `HTTP 401` from Firecrawl while the workflow's env listing shows the
key is injected.

- **Diagnose by probing the AGENT's shell, not the container.** `${#NAME}` = 0
  inside the agent's command means Hermes stripped it, even though the value is
  in the container and the workflow passes `-e NAME`. A pre-flight check that
  runs in `make` (outside Hermes) passes while the agent's own curl still 401s
  — the check must run inside the agent's command environment to prove the key
  is actually visible to the agent.
- **The escape hatch is the `_HERMES_FORCE_` prefix.** Forward the key as
  `-e _HERMES_FORCE_FIRECRAWL_API_KEY`; Hermes unwraps it to
  `FIRECRAWL_API_KEY` in the agent's command env. This is the only way a
  blocklisted name reaches the agent — a plain `-e NAME` is stripped, and
  `env_passthrough` registration cannot override the blocklist.
- **A fix that only corrects the variable NAME in the prompt does not fix a
  stripped key.** If the agent's curl still gets 401 after the prompt names the
  right variable, the key is being stripped, not misnamed — fix the env
  forwarding, not the prompt.
- **Add a test that fails when the agent's command environment cannot see the
  key** (assert the key is present in the env Hermes builds for the agent's
  commands), so a future change to the blocklist or the forwarding cannot
  silently re-break the scrape.

## Read the run's CONCLUSIONS before claiming a step ran in production

A merged change to a bot step is only production-proven by a run that actually
executes that step. The implementer sweep can conclude `guard: success / pick:
success / implement: skipped` — every candidate held (an in-flight/reviewed
issue), so the changed `implement` step never ran in production at all, and a
"green" run proves nothing about it. Before reporting that a fix was verified
in the pipeline: `gh run view <id> --json jobs` and confirm the step's
conclusion is `success` (not `skipped`), and read the `pick` reason
(`gh run view <id> --log | grep 'issue='`) when you expected an implementation.
While the queue yields nothing, the honest proof is driving the SHIPPED step
text locally against a real value until a real run exercises it — and then check
that run's log.

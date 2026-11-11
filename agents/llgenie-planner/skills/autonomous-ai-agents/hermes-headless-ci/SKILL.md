---
name: hermes-headless-ci
description: "Use when running Hermes CLI headlessly (CI, cron, Actions)."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, ci, github-actions, headless, automation, provider, nous, cache, makefile]
    related_skills: [hermes-agent, hermes-profile-config]
---

# Hermes CLI in headless/CI automation

Running `hermes -z "..."` (one-shot) on a CI runner / cron / agent. Covers the
non-obvious setup that costs a session each time: provider auth, the PATH env
gotcha, install caching, and keeping CI identical to local runs.

## 1. Provider auth — use a custom alias, not `--provider nous`

The bundled `nous` provider is `auth_type="oauth_device_code"`. That means
**a bare `NOUS_API_KEY` env var is ignored** (client_lifecycle only reads an
API-key env var when `auth_type == "api_key"`), and even
`hermes auth add nous --type api-key --api-key "$KEY"` does NOT satisfy the
OAuth state check (`resolve_nous_access_token` needs OAuth state).

Working fix — point at the Nous OpenAI-compatible endpoint with a **custom
provider alias**:

```bash
export NOUS_API_KEY="sk-nous-..."
hermes config set model.aliases.nous-deepseek.model deepseek/deepseek-v4-flash-0731
hermes config set model.aliases.nous-deepseek.provider custom
hermes config set model.aliases.nous-deepseek.base_url https://inference-api.nousresearch.com/v1
hermes config set model.aliases.nous-deepseek.key_env NOUS_API_KEY
hermes -z "..." -m nous-deepseek
```

**The CLI's own flags are the other trap — verify them by RUNNING the call, not by
reading the Makefile.** In current Hermes builds:
- `--alias` is **not a flag**: `hermes --alias X` fails with "'X' is not a `hermes`
  command". The alias is selected with `-m <alias>` like any model.
- **`-m` is the MODEL flag, not "message".** A smoke written as
  `hermes --max-steps 1 -m "Reply with exactly: ok"` sets the *model* to that sentence;
  the prompt belongs on `-z`.
- `--max-steps` does **not exist**; a step cap is not how you bound a headless run.
  One-shot work is `hermes -z "<prompt>" -m <alias> --reasoning <level> --yolo`.
- A wrapper that feeds the prompt on STDIN must consume it explicitly:
  `FIX_AGENT_CMD='hermes -z "$(cat)" -m nous-deepseek --yolo'`, invoked as
  `bash -c "$FIX_AGENT_CMD" <prompt`.

Always prove the wiring with one real call **inside the image**
(`docker run … hermes -z "Reply with exactly: ok" -m <alias> …` → `ok`). The fake
flags above parse as valid shell and fail only at run time, so a green build, a green
lint and a test that greps the Makefile all pass while the bot is dead on arrival.

## A workflow that cannot PARSE fails as an empty run, not as an error

GitHub does not report a YAML error on a bad workflow file. On `push` (or dispatch) it creates a
run with **zero jobs**, marks it failed, and the Actions tab shows "completed/failure" with an
empty job list — which reads as "the workflow did nothing", and is indistinguishable from a job
that never ran. Diagnose it by checking `.jobs` in
`gh run view <id> --json jobs`: an empty list means the file did not load, not that a step failed.

Two habits prevent it:

- **Never write an unquoted scalar containing `": "`** — in a step `name:` too, not just in values:
  `- name: Log in to GHCR (the default token: the credential that can create the package)` is
  invalid (`mapping values are not allowed here`). Drop the colon or quote the whole string.
- **Parse every workflow in a unit test**, not with substring assertions:

  ```python
  for f in sorted((REPO / ".github" / "workflows").glob("*.yml")):
      doc = yaml.safe_load(f.read_text())
      assert isinstance(doc, dict) and "jobs" in doc, f.name
      for job, spec in doc["jobs"].items():
          assert spec.get("runs-on") or spec.get("uses"), f"{f.name}:{job} runs nowhere"
  ```

  Tests that only `assert "some string" in workflow_text` pass happily on a file that cannot load.

## Pitfalls
- The model id must be **provider-prefixed** (`deepseek/deepseek-v4-flash-0731`),
  NOT bare `deepseek-v4-flash-0731` — the Nous endpoint serves them prefixed
  and returns HTTP 404 for the bare id. List available ids:
  `curl -s https://inference-api.nousresearch.com/v1/models -H "Authorization: Bearer $NOUS_API_KEY"`.
- Verify the alias works before wiring it into CI: `hermes -z "reply OK" -m nous-deepseek`.

## 2. PATH in Runner env is NOT shell-expanded

In a GitHub Actions `env:` block,
`PATH: "$HOME/.local/bin:$PATH"` is stored **literally** — `$HOME`/`$PATH` are
not expanded, so the next step still gets `command not found`. Fix: put
`export PATH="$HOME/.local/bin:$PATH"` at the top of each `run:` block, not in
an `env:` entry.

## 3. Install once, cache, then `hermes update`

Full install clones + builds the whole repo (~2 min). On a fresh runner it is
necessary once; after that, restore from cache and just update:

```yaml
- name: Cache Hermes install
  id: hermes-cache
  uses: actions/cache@v4
  with:
    path: |
      ~/.hermes
      ~/.local/bin
    key: hermes-${{ runner.os }}-${{ hashFiles('Makefile', 'scripts/**') }}

- name: Install Hermes CLI (first run)
  if: steps.hermes-cache.outputs.cache-hit != 'true'
  run: |
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="$HOME/.local/bin:$PATH"
    hermes --version

- name: Update Hermes CLI (cached)
  if: steps.hermes-cache.outputs.cache-hit == 'true'
  run: |
    export PATH="$HOME/.local/bin:$PATH"
    hermes update || echo "update skipped; using cached install"
```

## 4. Makefile = single source of truth; CI calls the same targets

Encapsulate every stage as a `make` target (`setup`, `search-a`, `search-b`,
`merge`, `validate`, `fix`, `refresh`) and have the workflows invoke
`make <target>`. Then `NOUS_API_KEY=... make refresh` reproduces the pipeline
locally, and CI is just the same commands on a runner — no drift between what
you test and what ships.

**Docker-wrapper variant.** When the pipeline needs Python deps + the Hermes CLI
baked in, make the public targets thin docker wrappers over `_`-prefixed host
recipes: `test: $(DOCKER_RUN) make _test` where `DOCKER_RUN` bind-mounts the repo
at `/workspace` and passes the API-key env vars through. Then `make test` runs
identically on a runner and locally, and the host's Python/pip/Hermes are never
relied on. Requires `make docker-build` first; the image is the cache key.

Pitfalls when the image is built by a hash-tagged CI registry (e.g. llgenie's
`scripts/ci_images.py`), each one a red pipeline discovered the hard way:

- **The CI build context is FLAT.** Such a registry copies each declared input
  file to a temp context root, so a Dockerfile that `COPY scripts/foo.sh` fails in
  CI with `failed to calculate checksum ... "/scripts/foo.sh": not found` even
  though the same build works from the repo root. `COPY foo.sh` is the working
  form; declare every COPYed file as an input of the image so its bytes are in the
  tag hash. Reproduce CI locally with the registry's own command (`ensure <name>`),
  never with a raw `docker build .` from the repo root — that hides this class.
- **A missing `--cache-from` ref fails the FIRST publish of a new image**
  (`failed to configure registry cache importer: ...:buildcache: not found`).
  Add `--cache-from type=registry,ref=<cache>` only when that ref is already
  published (`imagetools inspect` it first); an existing image never notices.
- **A bot's fix commit may beat you to a merge-induced staleness.** After a
  sibling PR merges, a test the fix-bot owns can start failing on YOUR branch
  (e.g. the merged test imports a module you renamed); expect a follow-up commit
  on your PR branch and rebase onto it rather than force-pushing over it.

Pitfalls when testing such a pipeline locally:
- **The `patch` tool's fuzzy matcher can corrupt hyphenated YAML keys and
  `.md` filenames.** Editing a workflow key like `timeout-minutes` or a path
  like `gather-data.md` can silently produce `timeout-min-minutes` or
  `gather-data.md.md` — the matcher duplicates a token instead of replacing it.
  After patching a YAML key or a filename, re-read the line and confirm the
  exact token; if the patch tool mangles it, do the exact-key edit with a
  direct shell string substitution instead of retrying `patch` (it tends to
  re-mangle the same way).
- **Negative-path tests print `FAIL:` lines that are NOT failures.** A validator
  suite that asserts it *catches* bad data (missing model, stale timestamp,
  hand-edited README, malformed fixture) emits `FAIL: ...` for each deliberate
  rejection. Read the summary line (`PASSED N | FAILED 0`) and the exit code,
  not the `FAIL:` lines — those are the assertions passing. Misreading them as
  red is a false alarm that wastes a session.
- **`make merge` / `make requirements` dirty the working tree.** Running the
  pipeline locally regenerates `models.json` + `README.md` and writes a new
  timestamped snapshot (untracked). Expect these side effects and check
  `git status` after a local run; re-run `make validate` to confirm the
  regeneration is still consistent before committing.
- **`docker-build` is slow at the export step** — the image export can exceed a
  default 420s tool timeout even when the build is healthy. Run it alone with a
  long window; a timeout-kill during export is not a build failure (the image
  still exists and a re-run completes).
- **Key-hungry targets fail at the auth boundary, not the plumbing.** `search-*`,
  `fix`, `refresh` invoke Hermes/Firecrawl and return `HTTP 401: API key
  invalid/blocked/out of funds` when `NOUS_API_KEY`/`FIRECRAWL_API_KEY` are
  unset. The docker wrapper and Hermes invocation work fine — the failure is
  purely missing credentials. Set the keys in the shell before running these.
- **When `make test` is a docker wrapper and the host lacks the venv/pytest,
  drive each test file directly.** The pipeline's tests are self-verifying
  Python scripts: `for t in <names>; do python3 tests/test_$t.py; done` prints
  `PASSED N | FAILED 0` per file (rc 0 = pass) — read that summary, not the
  volume of `ok ...` lines. Some are slow (a faketime/make-wrapped decision
  test needs > 120s), so give the loop a generously long window or run the
  slow file on its own; a timeout mid-test is not a failing test.

## 4b. Agent-driven pipeline failures (Hermes/LLM in CI)

When an LLM agent drives the pipeline, failures are often NOT code bugs:

- **Model output truncation.** `The model's reply was cut off before it
  finished (it hit its output length limit)` means the model hit its
  `max_tokens` cap mid-action and the incomplete action was dropped — the
  `make` step then fails with `Error 2`. Fix: raise the alias's `max_tokens` in
  the setup step (`hermes config set model.aliases.<alias>.max_tokens`). A long
  multi-query search is exactly what trips the default cap. **8000 is NOT
  enough for heavy searches** — a short search completes at 8000 while a
  heavier one (more queries, more captured models) truncates mid-payload at the
  same setting. The model card supports far higher; size the cap to the
  heaviest single search, not the lightest. Also raise `context_window` to the
  model's ceiling (`hermes config set model.aliases.<alias>.context_window`)
  — a long AGENTS.md + skill + scraped-page prompt can otherwise be squeezed
  even when output tokens are fine. Verify the values actually took effect by
  running the setup step in the container and grepping its output for
  `✓ Set ... max_tokens = <N>` / `context_window = <N>` — `make _setup` fails
  silently on a bad key.
- **'No visible answer was produced ... reasoning consumed the entire budget
  each time' is NOT fixed by raising max_tokens.** A reasoning model just thinks
  longer; at a 384K cap it still burns it all and writes nothing (exit 2). Pass
  `--reasoning low` (CLI flag, overrides agent.reasoning_effort per run) on
  mechanical gather prompts; drive it from one Makefile var. Use medium for a
  diagnose-and-fix agent.
- **A headless `hermes -z` run that needs input DETACHES instead of failing
  the reason.** When the run hits anything `--yolo` does not cover (a
  repo/agent-declared shell hook, a tool that asks a question), the CLI prints
  `Input required; detached without cancelling. Resume this session
  interactively.` and exits non-zero after burning whatever time it already
  spent — the log shows only `Error 2`, never what asked. `--yolo` bypasses
  dangerous-command approval PROMPTS only; `--accept-hooks` is a SEPARATE flag
  that auto-approves declared hooks, so a one-shot recipe that must never block
  passes BOTH, from one Makefile variable so a new recipe cannot omit one.
  Confirm which flags exist by running `hermes --help | grep -iE
  'input|interactiv|yolo|detach|approv'` at the pinned version — never assume a
  flag from another release.
- **`--yolo` and `--accept-hooks` do NOT answer the agent's own `clarify`
  question, and that is the most common way a one-shot leg dies on input.** The
  agent calls `clarify` (asking the user a decision), Hermes detaches with
  `Input required; detached without cancelling`, exit **3**, the tree is
  unchanged — and the wrapper reports it as "produced no implementation" /
  "changed nothing", which sends the reader after data, keys or an alias. Two
  fixes, both needed:
  1. **Every prompt that runs unattended must forbid input**, in its own words:
     "You are UNATTENDED: never ask a question and never wait for input; if a
     decision is genuinely open, take the path that needs none (a refine with
     its reason, a close with cited evidence) or the safest reversible choice,
     and state it in your output — a question fails the run." A prompt that is
     silent about this is a latent exit-3. Keep the rule in every leg's prompt
     (triage, implement, refiner, docs, fetch) and in the fix-bot's rules file,
     and lock it with a test that greps the real prompts, so it cannot be
     dropped from one of them.
  2. **Name the exit code in the failure path**: rc `3` from the leg means "the
     agent asked for input", reported separately from a real no-change run.
     Print that before the generic message; a blanket "changed nothing" is the
     misleading diagnosis in this bullet.
- **A bot step that drives Hermes must surface the agent's own last lines on
  failure, not just `rc=N`.** Wrap `make <target>` as `2>&1 | tee work.log` and,
  on a non-zero rc, put the log's tail into the run/issue/PR — a red job whose
  only output is a return code costs an hour of log archaeology per occurrence.
- **A `hermes -z "..."` recipe line WITHOUT a trailing `\` makes the next
  line (`-m <alias> --yolo`) a separate make command.** Hermes then starts with
  NO alias and auto-picks any provider key in the env (e.g. `HF_TOKEN` ->
  `Hugging Face rejected your API key ... HTTP 403 ... Inference Providers`);
  with no such key it exits 1 silently. Diagnose with `make -n <target>`: the
  `-m` line printed on its own = broken continuation. Guard: validator requires
  every `hermes -z` line to end in `\`.
- **Validation inside a gather/refresh pipeline must be SOFT, not fatal.** If
  the pipeline runs `_validate` with `&&` chaining, a data-quality failure
  aborts the run BEFORE any "commit + open PR" step — the new data is stranded,
  no PR is opened, so the PR-CI validator never sees it and the auto-fix bot
  has no PR to repair. Keep gather/merge HARD (a broken merge must abort), but
  make validate/test log-and-report with exit 0 so the merged data always lands
  as a PR; the PR-CI validator then flags issues and the fix bot repairs them
  on the PR branch.
- **Auto-fix bot scope.** A fix bot triggered on `workflow_run` of the PR-CI
  workflow only fires for PR-branch failures — a manual dispatch on `master`
  (no open PR) is skipped by design. Don't expect it to repair a refresh-bot
  failure on master; the refresh must land a PR first for the loop to engage.
- **`gh pr create` from a workflow can be blocked by a repo setting, not the
  workflow.** The pipeline can commit and push the branch fine, then fail only
  at PR creation with `GraphQL: GitHub Actions is not permitted to create or
  approve pull requests (createPullRequest)`. `permissions: pull-requests:
  write` in the workflow is NOT enough — GitHub blocks Actions from
  creating/approving PRs unless the repo setting **"Allow GitHub Actions to
  create and approve pull requests"** is enabled (Settings → Actions → General
  → Workflow permissions). This is a repo-level toggle, not a code fix; a
  future session hitting it must tell the user to flip the setting (or use a
  PAT as `GH_TOKEN`).
- **Parallelize independent agent searches.** When each search writes its own
  output file (e.g. `data/raw/<backend>-<UTC>.json`), the searches are
  independent — run them with `make -j4` instead of sequentially. Setup/config
  must still run first so the alias is configured before the parallel spawn.
  This cuts the search phase from the sum of all searches to roughly the
  slowest single one.
- **Narrow the search window for a daily refresh.** A pipeline that runs daily
  does not need a 30-day search window — it re-scans the same old posts every
  run, wasting time and tokens. A 3-day (or 7-day) window pulls only content
  since the last run and speeds each search up.  Size the window to the cadence,
  not to the retention policy (retention and search window are separate).

## 4c. Repointing the model pin (switching the SKU that drives the repo)

One Makefile var (`HERMES_MODEL`) usually feeds every `hermes -z` call, but the
old SKU's id is also quoted elsewhere. When switching:

- **Resolve the exact target id from the endpoint, never guess.**
  `curl -s https://inference-api.nousresearch.com/v1/models -H "Authorization: Bearer $NOUS_API_KEY"`
  — ids are provider-prefixed (`deepseek/deepseek-v4.1-flash`), and the
  documented field set differs between SKU versions (e.g. V4 → V4.1 adds
  `reasoning_effort` next to `reasoning`).
- **Re-measure the output cap; don't carry it blind.** A newer SKU may declare
  NO `top_provider.max_completion_tokens` where its predecessor declared a cap.
  When it's absent, KEEP the previously-measured cap and mark it "measured on
  the predecessor" — a larger `max_tokens` is accepted SILENTLY and clamped, so
  raising it blind buys nothing. Offer a live re-measurement as a follow-up
  issue instead of assuming headroom.
- **Grep the whole tree for the old pin and update every reference:** Makefile,
  the budget-guard test (a MODEL constant + its check text), AGENTS.md model
  notes/descriptions, workflow PR-body strings, skill/docs files, script
  comments. Intentional history ("the 65536 was measured on the predecessor")
  is fine to keep — only the live pin and stale quotes change.
- **Keep a live-smoke on the pin-changing PR:** one real `hermes -z` call
  through the alias is the proof the new model answers on the endpoint — a
  green live-smoke beats a silent swap with no live validation.
- **A green PR may auto-merge.** Some of these repos' `qa-validate` job
  auto-merges (squash + branch delete) via the workflow PAT; `mergedBy` then
  shows the PAT owner's login even though YOU did not merge. Report it as the
  repo's own auto-merge (its documented design), never as a manual merge you
  performed.

Wiring a NEW leg end to end has its own set of gates that only red after the code is written
(root-owned change dir, byte-identical guard step, odd unowned cron, generated dispatch table,
run-input roster, ticking tasks before the loop, fork-vs-upstream push):
`references/bot-leg-wiring.md`.

## 5. Secrets wired as workflow env, never committed

Store tokens as repo secrets and reference by name; keep them out of files and
shell history:

```yaml
env:
  NOUS_API_KEY: ${{ secrets.NOUS_PORTAL_API_TOKEN }}
  FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
```

Set a secret without printing it to argv/history:
`printf '%s' 'sk-...' | gh secret set NAME -R owner/repo`.

**When a tracked file must contain a credential's VARIABLE NAME, verify the literal
landed — a key-shaped name can arrive elided.** Writing `.hermes/skills/*/SKILL.md`
or a prompt file that must say `${FIRECRAWL_API_KEY}` can put an elided form
(`${FIRE...Y}`) into the file: redaction applies to the agent's own message traffic
as well, in both directions, and the elided shape is exactly the defect a repo's own
key guard exists to catch — committed, it recreates the bug. Never conclude from the
rendered output that the literal is right (the rendering is what is masked). Verify
without printing it: `t.count(NAME)` / a hash of the line, or grep for a distinctive
`...` substring that must NOT occur. If it is mangled, write it from concatenated
fragments (`"FIRE" + "CRAWL" + "_API" + "_KEY"`) inside a script, then re-count.

Verify a headless run leaked no secret by grepping the log, not by reading a
config. GitHub masks every secret VALUE in step `env:` blocks and stdout as
`***`, so a log listing `NOUS_API_KEY: ***` beside the variable NAME is normal
and safe — the leak shapes to check are a VALUE passed on a command line
(`-e KEY=$KEY`, `--build-arg KEY=$KEY`) or printed. Pass creds to `docker run`
by NAME only (`-e NOUS_API_KEY`, never `-e NOUS_API_KEY=$KEY`), and confirm the
fetched run log matches 0 token shapes
(`gh run view <id> --log | grep -cE 'ghp_|gho_|ghs_|github_pat_|sk-|Bearer [A-Za-z0-9]'`)
in addition to the tree gate.

## 5b. Getting a key into the AGENT's shell inside a container

A credential the container gets as `-e KEY=x` reaches the Hermes PROCESS's env,
but NOT the agent's shell/terminal tool — Hermes strips it, so a `run: echo
"$NOUS_API_KEY"` inside the bot shows empty. This is a Hermes behavior, not a
broken container: a bare `-e KEY=x` is only enough for the Hermes process to
read its own `key_env`; work the agent does through its shell needs the key in
the CHILD environment too.

The mechanism that works: forward each key as **`-e _HERMES_FORCE_<NAME>`**
(Hermes's only form that passes a real value through to the agent's child
shell). Set it in the container entry from the already-plain `$NAME` so the
VALUE still never appears on a command line or in argv:

```makefile
DOCKER_RUN = docker run -e NOUS_API_KEY \
	-e _HERMES_FORCE_NOUS_API_KEY=$$NOUS_API_KEY \
	-e FIRECRAWL_API_KEY -e _HERMES_FORCE_FIRECRAWL_API_KEY=$$FIRECRAWL_API_KEY \
	...
```

- **Keep ONE list of keys** (`AGENT_SHELL_KEYS`) that both the forward line and
the guard read, so adding a key to the container cannot be forgotten in the
agent's shell.
- **Add a guard that fails when the agent's command environment cannot see a
key** — and run it INSIDE the bot image, not the host. The host's shell and the
container's bidirectionally contradict each other (a host probe can show the
key visible while the bot's shell hides it, or vice-versa). Detect ``in-container``
via `/.dockerenv` so the guard runs where it is meaningful, and have it print
key LENGTHS, never values.
- **Test through the real tool, and prove the direction**: drive the check by the
same shell setup Hermes uses, once against the OLD wiring (must go RED) and once
against the new (must go GREEN), with the guard wired into the live key-having
job (e.g. qa-validate's `live-smoke`) so the real secrets exercise it.
- **The `_HERMES_FORCE_` form does NOT rescue the Python/`execute_code` tool** —
its children still get the keys stripped, so an agent-driven scrape must be
pinned to the terminal tool in the prompt, not expected to read a key from
`execute_code`.

## 6. Fetching Cloudflare-protected mirrors (e.g. the lightbrd X mirror)

Some preferred data mirrors sit behind Cloudflare and refuse raw
`urllib`/`curl` (HTTP 403). A **Firecrawl scrape API call passes** and returns
real content:

```python
payload = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": False})
req = urllib.request.Request("https://api.firecrawl.dev/v1/scrape", data=payload.encode(),
    headers={"Content-Type": "application/json",
             "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
    method="POST")
md = json.loads(urllib.request.urlopen(req).read())["data"]["markdown"]
```

Do not claim a mirror is "down" when raw urllib 403s — renderer/API paths that
pass Cloudflare still work. Ask the user for a Firecrawl token and store it as
a secret before relying on this path.

## 7. Give each bot leg its own project skill

A headless bot's contract (what it may write, what it must produce, what it must
never do) belongs in a Hermes **project skill**, not in an inline `hermes -z`
string. Layout: `.hermes/skills/<name>/SKILL.md` with `## Inputs`, `## Output`
(the ONE file the leg may write) and `## Rules`. The leg preloads it:

```makefile
_issue-triage:
	hermes -z "Follow the preloaded skill issue-triage. Its Input is issue.md and its Output is triage.md." \
	  -s issue-triage,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
```

The inline prompt becomes a pointer plus this run's parameters (target < 400
characters); the shared rules (e.g. "unattended, never ask a question") live in
ONE shared skill instead of being repeated in every leg.

**A leg that must DECIDE gets a deterministic precondition, not a prompt.** Split the bot into a
`-brief` step that a script answers offline (is there work? what are the measured facts?) and the
agent leg that only judges. Every step that reads a secret or starts the image is gated on the
brief's verdict (`if: steps.brief.outputs.action == 'review'`), so the scheduled run costs nothing
when there is nothing to do, and a skipped run is diagnosable from its own printed reason. Put the
precondition in the SCRIPT, never in a scenario-scoped workflow `if:` that silently skips.

**A bot that judges a PR must read the PR's TREE, not the base branch's.** Checking out `main` and
then reviewing "the PR" reviews last week's data — measured: the store the review described was the
one on main while the PR carried a newer one. Check the PR head out first (`gh pr checkout <branch>`,
`continue-on-error` so a missing PR still reaches the brief, which then answers `skip`).

**Tolerate `gh pr checks`' non-zero exits.** It exits 8 while a check is pending and 1 when a PR has
none: both are an answer ("not green yet"), not a broken command, so pass an allowed-codes tuple in
the runner instead of letting `subprocess`-with-check raise and turn the precondition into an error.

**Report grouped, not per case.** One defect repeated across 16 (arch, vram, ram) cases is ONE line
with a case count and one reproducible example; per-case output buries the shape (the first 60 rows
were one model, which read as "92 findings, one cause" and was wrong).

**Registration is the failure point.** Hermes reads skills from its home and
`skills.external_dirs`; an unregistered checkout makes `-s <name>` resolve to
nothing and the leg runs with NO contract while reporting success. Register at
image build time and READ THE VALUE BACK:

```bash
hermes config set skills.external_dirs "[\"/repo/.hermes/skills\"]"
hermes config get skills.external_dirs   # prove it landed, or fail the build
```

On a pinned older CLI (`hermes-agent==0.19.0`) `config set` stores that JSON
literal as an OPAQUE STRING and resolves zero directories — write a real YAML
list into `config.yaml` instead (`external_dirs:\n  - /repo/.hermes/skills`),
then `config get` to verify. A registration script that writes YAML and checks
it works on both new and pinned CLIs; see
`references/project-skills-registration.md`.

**Gate the legs.** A checker in `ci-unit` must fail a leg with no `-s`, an
unknown skill name, a frontmatter `name` that disagrees with its directory, a
skill missing `Inputs`/`Output`/`Rules`, a prompt over the budget, an inlined
unattended contract, a skill no leg preloads, or a returned old rules file.

**Prove loading without a model call.** `agent.skill_commands.build_preloaded_skills_prompt`
is exactly the function `hermes -z "…" -s <name>` calls before the first turn.
Feed each leg's `-s` list to it against a home registered by the image's own
script and assert every name resolved and the skill's description reached the
rendered prompt — plus the negative: an unregistered home resolves nothing.
This is a real load proof at zero model cost (recipe in the reference).

**When an inline prompt moves into a skill, repoint the tests at the skill.**
Tests that asserted literal prompt text (`"(1)"`, `"Do not commit"` in the
Makefile recipe) must read the `SKILL.md` instead — the skill is the canonical
source, so align the TEST to the skill's wording, not the skill to the old
assertion. Keep asserting the leg preloads it (`-s <name>` in the recipe).
Grep the test tree for the quoted rule before editing the recipe — a prompt-text
assertion fails on the assertion string, not on the behaviour.

**Finishing a HALF-done seam: the rule VARIABLES are still the rulebook.** A leg
that already passes `-s <skill>` can still carry its whole contract inline, and the
usual hiding place is a Makefile variable expanded into four recipes
(`ENGINE_ASK`, `DIM_ASK`, `SCRAPE_ASK`-style blobs) that the skill restates in
different words. Two homes for one rule, and nothing compares them. Complete the
migration as a shape, not a trim:

1. Move the variable's TEXT into the skill (verbatim in substance — the rule, not
   a summary), then DELETE the variable from the Makefile.
2. Leave the recipe with parameters only — the backend/run name, the per-run lists
   the guards read (`$(MODEL_QUERIES)`, keyword lists), the write command. Lists
   that a script or test already parses are PARAMETERS, not rules: keep them in the
   recipe or you move the drift instead of removing it.
3. Shrink the gate's pointer budget until it can FAIL (a few hundred characters per
   leg). A budget loose enough for the old rulebook proves nothing — that is how the
   half-migration stayed green.
4. Make the gate assert the retired rule ARRIVED: for each retired marker, it must
   appear in the skill it moved to and in NO recipe. Migration without that check
   can silently drop a requirement.

**A prompt-format change also breaks the parsers that read the prompt.** Before
rewriting a recipe's wording, grep `tests/` AND `scripts/` for the shape being parsed,
not just for the rule's prose: a smoke/query-extractor that regexes the old prompt
sentence (`keywords ONLY (…)`, `Search with <X> keywords`) silently returns an empty
list afterwards — the suite then fails on "keywords drift" for every backend while the
data is fine. Update the parser in the SAME change, to the same single source.

**A rule stated in a variable is unenforceable by length alone.** When the gate only
measures prompt size, a 2 KB rulebook passes as "a pointer"; the durable signal is
"this target restates marker X" plus "marker X is absent from every recipe", which
survives rewording.

**Keep the bot-skill directory distinct from the engine-skill directory.** Engine
skills describe inference servers and are read by the params generator; they are
never loaded by an agent. Bot contracts live in their own directory so the two
gates cannot confuse them.

**Pitfalls.**
- A container run from a git **worktree** fails every `git` call with `fatal:
  not a git repository: /host/path/.git/worktrees/<name>`: the worktree's
  `.git` is a file pointing at an absolute host path that is not mounted. The
  repo Makefile's `WORKTREE_MOUNT` mounts the parent `.git`; a hand-rolled
  `docker run -v "$PWD":/workspace` does not. Run `make test-unit`, or mount the
  parent `.git` dir too.
- `git` as root in a mounted volume returns rc 128 ("dubious ownership"). Use
  `git -c safe.directory=<path> -C <path> …` in tests rather than mutating the
  global git config.
- `hermes config set skills.external_dirs '["/a","/b"]'` on a newer CLI is
  fine; on the pinned CLI it is the silent-zero bug above. Always read back.
- **Drive multi-line edits from a script file, not a shell heredoc.** A heredoc
  that rewrites a Makefile or test file gets mangled by quoting and leaves a
  half-edited tree; write the edit as a small Python script, run it, then read
  `git diff` to confirm the intended span moved and nothing else did.
- **A full unit suite can outlive a foreground tool call.** Run it as a tracked
  background process with notify-on-complete and read its `rc=` line when it
  lands; polling in a foreground loop burns the window and the suite's own
  progress output tells you nothing the exit code does not.

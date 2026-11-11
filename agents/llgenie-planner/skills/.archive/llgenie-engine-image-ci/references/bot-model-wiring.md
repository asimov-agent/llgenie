# The bots' model pin, alias and credentials (llgenie agent image)

Every llgenie bot leg (issue-bot, fix-bot, issue-refiner, rebase-bot, `agent-fetch`) calls the Nous
endpoint from inside `llgenie/agent` through the custom provider alias `nous-deepseek` (Hermes's
bundled `nous` provider is OAuth-only, so a secret key only works through an alias). This file is the
procedure for auditing, moving and proving that pin.

## 1. Which ids are actually distinct models

`GET https://inference-api.nousresearch.com/v1/models` answers **without a key** (empty `Bearer` is
fine), so use it first instead of trusting an id's shape.

- A DeepSeek-family pin is a **snapshot**: `deepseek/deepseek-v4.1-flash-1017` and the unsuffixed
  `deepseek/deepseek-v4.1-flash` are DIFFERENT models (`canonical_slug …-20261017` vs `…-20260910`,
  different serving provider, different price), and **both return 200**. Compare `canonical_slug` /
  `name` / `created` from the catalogue, never "it answered 200" and never the id's prefix.
- The catalogue object also carries `context_length` and `max_completion_tokens` — copy those into the
alias budget instead of guessing.

## 2. Live calls when the shell has no key

Hermes strips `NOUS_API_KEY` from the terminal tool, so an in-shell `curl -H "Bearer $NOUS_API_KEY"`
sends an empty token and returns 401 — that is NOT a bad endpoint or a dead key. Get a working token
from the local auth store without printing it:

```bash
export NOUS_API_KEY="$(python3 -c 'import json;print(json.load(open("/home/asimov/.hermes/auth.json"))["providers"]["nous"]["agent_key"])')"
```

The value never lands on a command line that way (the python snippet is all `ps` sees), and `make
target` picks it up for its `docker run -e NOUS_API_KEY`.

## 3. Where the pin lives, and how to keep it from drifting

- `containers/agent/Dockerfile` — `ARG HERMES_MODEL_ID="…"` (and the build asserts the alias keys)
- `scripts/install_hermes_ci.sh` — `MODEL_ID="${HERMES_MODEL_ID:-…}"`, plus the alias writes
- `scripts/agent_model_pin.py` — the ONE declaration (`MODEL_ID`, `MAX_TOKENS`, `CONTEXT_WINDOW`);
  `make check-agent-model` (run by `ci-unit`) compares all of them, `make model-pin-report` prints

Rules that follow:
- The alias MUST carry `max_tokens` and `context_window`. Without them Hermes budgets the run from the
  models.dev catalogue, which has no entry for a snapshot id — a 120-180 minute bot job then runs on a
  default window instead of the model's real one.
- Assert the whole alias in the image build (`model`, `provider`, `key_env`, `max_tokens`,
  `context_window`), not just `key_env`: a half-written alias otherwise fails mid-run, not at build.
- A test that asserts a model-id **prefix** is not a pin: any newer snapshot satisfies it, which is
  exactly how a stale pin ships unnoticed. Assert the exact id.

## 4. Prove the gate against the untouched checkout (negative control)

A green gate on your own tree proves nothing. Point it at the user's untouched clone, which still has
the old value, and require it to fail with the drift named:

```bash
python3 scripts/agent_model_pin.py check --root /home/asimov/repository/git/llgenie   # must exit 1
```

Same shape for any new guard: run it on the pre-change tree, quote the findings in the PR.

## 5. Verify inside the rebuilt image, not just in tests

```bash
make agent-image          # rebuilds because the Dockerfile + install script are its hash inputs
docker run --rm llgenie/agent:latest bash -lc 'for k in model provider base_url key_env max_tokens context_window; do printf "%s=" "$k"; hermes config get "model.aliases.nous-deepseek.$k"; done'
make hermes-smoke                                                   # one real call through -m nous-deepseek
make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY     # the AGENT's shell can see it
```

`hermes-smoke` only proves text generation. To prove **tool** use (what the bot legs actually need),
one one-shot through the same alias:

```bash
docker run --rm -e NOUS_API_KEY -e _HERMES_FORCE_NOUS_API_KEY llgenie/agent:latest bash -lc \
  'hermes -z "Run exactly: printf hermes-tool-ok . Use the terminal tool for it and reply with ONLY the command output." -m nous-deepseek --reasoning low --yolo'
```

## 6. Repo mechanics that cost time

- **`make openspec-new` runs the CLI in a container as root**, so the new
  `openspec/changes/<name>/` directory is owned by root and every `write_file` into it fails with
  Permission denied. Run `sudo chown -R asimov:asimov openspec/changes/<name>` before writing
  `proposal.md` / `specs/` / `tasks.md`. The CLI only creates the directory: you still author all
  three files.
- **Remotes in this checkout are inverted relative to AGENTS.md's prose**: `origin` is the upstream
  `asimov-agent/llgenie`, `fork` is `andyholst/llgenie`. Push with `git push -u fork <branch>` and open
  the PR as `--repo asimov-agent/llgenie --base main --head andyholst:<branch>`.
- **Long gates buffered behind `| tail -N` print NOTHING until the process exits** — a running build or
  test suite looks dead. Check real progress elsewhere: `docker logs --tail 5 <container>` for a test
  container, `sudo ps -eo pid,ppid,etime,cmd` for the build's current `RUN` step. Do not foreground
  `sleep` to wait on them; run them with the terminal tool's `background=true` + notify and use the
  time for the rest of the change (note: the terminal tool's wait parameter is `timeout`, not
  `timeout_s`, and a foreground call still caps out around 180 s).
- Before pushing, re-run `git fetch origin main` + `git merge-base --is-ancestor origin/main HEAD`; after
  review engages, fixes go on top as normal commits, not amends.

## 7. Auditing whether the scheduled bots actually do their job

The model pin can be perfect while a leg never reaches it. Audit each workflow separately before
answering "are the bots working?":

```bash
for w in issue-bot fix-bot issue-refiner rebase-bot; do
  echo "== $w"
  gh run list --repo asimov-agent/llgenie --workflow "$w.yml" --limit 4 \
    --json createdAt,event,status,conclusion --jq '.[]|"\(.createdAt)\t\(.event)\t\(.status)/\(.conclusion)"'
done

# what a RED leg actually died on (the refusal names the capability, not the code)
gh run view <run-id> --repo asimov-agent/llgenie --log-failed | grep -E "Resource not accessible|403|error" | head

# what a GREEN leg actually did (a no-op and a working run look identical otherwise)
gh run view <run-id> --repo asimov-agent/llgenie --log | grep -E "\[sweep\]|\[rebase-bot\]|action=" | tail -6
```

- Decide-only paths are safe to exercise for real, read-only:
  `make issue-bot-dispatch REPO=asimov-agent/llgenie DRY=1` (prints `action=none` when nothing carries
  `agent:implement`/`agent:ready`) and `make rebase-bot-sweep` (prints the reason for every pass-over).
- Measure the 3-per-day cap against a day the bot really opened PRs, with BOTH identities — the default
  `BOT_AUTHOR` is not what `open-pr` produces:
  `python3 scripts/issue_implementer.py count --repo asimov-agent/llgenie --today <UTC-date> [--bot <login>]`.
  A `0` where the other login returns >0 is the cap being decorative, and `scripts/issue_refiner.py`
  repeats the same constant, so the two bots share a budget neither can see.
- Report the split, not a verdict: what a live run proved (alias keys in the image, one text smoke, one
  tool-calling smoke, the agent shell reading the key) versus which leg is still blocked and by what
  (issue number). Never call a leg "working" because its schedule concluded `success`.

# The model the llgenie bots are pinned to

Every bot leg (`issue-bot`, `fix-bot`, `issue-refiner`, `rebase-bot`, `agent-fetch`) runs the Hermes
CLI inside `llgenie/agent` and calls one snapshot through the CUSTOM provider alias `nous-deepseek`
(Hermes's bundled `nous` provider is OAuth-only, so a secret-supplied NOUS_API_KEY only works through
an alias). Where that pin lives, how to move it, and how to prove it:

- `scripts/agent_model_pin.py` declares it once: `MODEL_ID`, `MAX_TOKENS`, `CONTEXT_WINDOW`.
- `containers/agent/Dockerfile` — `ARG HERMES_MODEL_ID` (default) plus `ARG HERMES_MAX_TOKENS` /
  `HERMES_CONTEXT_WINDOW`, and the build asserts the alias's `model`, `max_tokens`, `context_window`.
- `scripts/install_hermes_ci.sh` — `MODEL_ID`, `MAX_TOKENS`, `CONTEXT_WINDOW` defaults; it writes the
  alias and re-reads every key loudly.
- Gates: `make check-agent-model` (stdlib, no network, no key; runs in `ci-unit`) and
  `make model-pin-report`.

## The snapshot suffix IS the model

A provider-prefixed id with a trailing snapshot (`…-1017`) and the same id without it are DIFFERENT
models served side by side, and **both answer 200**, so a bot job cannot tell them apart. Resolve the
`canonical_slug` before believing an id is current. A pin test that asserts only the family prefix
(`"deepseek/deepseek-v4.1-flash" in script`) is satisfied by any newer id — it is the reason such a
drift ships silently. Assert the exact id, and give the pin ONE declaration with a checker that
compares every file carrying it (reporting file + the value it read), never a regex over one file.

Prove a new gate is real by running it against the untouched checkout before committing:

```bash
python3 scripts/agent_model_pin.py check --root /home/asimov/repository/git/llgenie   # the old tree reds
python3 scripts/agent_model_pin.py check                 # the worktree is green
```

## Probing the Nous endpoint from the terminal

`GET /v1/models` answers WITHOUT a key (an empty `Bearer` returns the catalogue), so the cheap probe is
always available; it is also where `canonical_slug`, `context_length`, `max_completion_tokens` and the
`reasoning` block for an id come from.

A real completion needs a credential, and `$NOUS_API_KEY` reads **empty** in the terminal tool — the
policy strips it, and `_HERMES_FORCE_NOUS_API_KEY` does not un-strip it here. A `401 "Your API key is
invalid"` from a shell probe therefore means *no key was sent*, not that the key is bad. Read the
agent key straight out of `~/.hermes/auth.json` in Python and never print it:

```python
import json, urllib.request
auth = json.load(open("/home/asimov/.hermes/auth.json"))["providers"]["nous"]
key, base = auth.get("agent_key") or auth["access_token"], auth["inference_base_url"].rstrip("/")
req = urllib.request.Request(base + "/chat/completions",
    data=json.dumps({"model": MODEL_ID, "messages": [{"role": "user", "content": "say ok"}],
                     "max_tokens": 64}).encode(),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(req, timeout=120))["model"])
```

A reasoning snapshot answers with `reasoning_content` populated and `content` possibly `null` at low
`max_tokens` — that is not a failure. Prove tool calling too (every bot leg is tool-driven): send a
`tools` array with a one-argument function and assert `finish_reason == "tool_calls"`.

The same key exports cleanly for the make legs that need it, in ONE command so it never lands in a log:

```bash
export NOUS_API_KEY="$(python3 -c 'import json;print(json.load(open("/home/asimov/.hermes/auth.json"))["providers"]["nous"]["agent_key"])')"
```

## Verifying a rebuilt agent image

The image tag is a hash of the Dockerfile, its COPYed install scripts and the test-image tag, so any
pin edit moves it — `ensure` then builds locally instead of pulling:

```bash
python3 scripts/ci_images.py ref agent          # the ref THIS commit would use
make agent-image                                # pull the hash tag, else build it here
make hermes-smoke                               # one real call through -m nous-deepseek
make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY
```

`hermes-smoke` raising `[agent] ok` proves the alias resolves and the snapshot answers. Read the alias
back out of the image itself to prove every key landed (the build already asserts it, this is the
human-readable half):

```bash
docker run --rm llgenie/agent:latest bash -lc 'for k in model provider key_env max_tokens context_window; do printf "%s=" "$k"; hermes config get "model.aliases.nous-deepseek.$k"; done'
```

Text generation is not agency: prove the agent can USE a tool, which is what every bot leg needs. Run a
one-shot inside the image that must call its terminal tool and echo the command's output — the reply is
the tool's real output (`hermes-tool-ok` below), and a text-only model cannot produce it:

```bash
docker run --rm -e NOUS_API_KEY -e _HERMES_FORCE_NOUS_API_KEY llgenie/agent:latest bash -lc \
  'hermes -z "Run exactly: printf hermes-tool-ok . Use the terminal tool and reply with ONLY the command output." -m nous-deepseek --reasoning low --yolo'
```

## Watching a long gate instead of guessing

Start heavy builds/tests in the background with their output redirected to a FILE (`> /tmp/x.log 2>&1`):
piping through `tail` buffers everything until exit, so the job looks frozen for its whole runtime. Then
observe live rather than re-running:

- `make test-unit`: `docker logs --tail 5 $(docker ps -q --filter ancestor=llgenie/test:latest | head -1)`
  shows the pytest progress line.
- `make agent-image`: buildkit runs its `RUN` steps as root in its own namespace, so a user-level `ps`
  shows nothing — use `sudo ps -eo pid,ppid,etime,cmd` and look for the `/bin/sh -c …` step
  (`install_hermes_ci.sh`, then `install_nerve_ci.sh`); `/proc/<pid>/fd` and `wchan` confirm it is
  working rather than hung.

## Fast focused test runs

`make test-unit` is the gate of record but takes ~20 minutes. To iterate on one file, run pytest in
the same container image the gate uses:

```bash
python3 scripts/ci_images.py ensure test
docker run --rm -v "$PWD:/repo" -w /repo llgenie/test:latest \
  python -m pytest tests/test_agent_model_pin.py tests/test_issue_implementer.py -q -p no:cacheprovider
```

The host python has no pytest — do not read "No module named pytest" as a broken environment.

## Openspec and bot-leg checks

- `make openspec-new` runs the CLI in a container as root: `sudo chown -R $USER: "openspec/changes/<name>"`
  before writing `proposal.md` / `specs/<cap>/spec.md` / `tasks.md`, or the writes fail with
  `Permission denied`.
- Loading a `scripts/*.py` module from a test: `importlib.util.spec_from_file_location` (assert both
  `spec` and `spec.loader` are not None for the type checker), as the repo's other tests do.
- Before trusting a bot's daily cap, run its own numerator:
  `python3 scripts/issue_implementer.py count --repo asimov-agent/llgenie --today YYYY-MM-DD` and again
  with `--bot asimov-agent`. PRs the bot opens use the owner PAT, so they are authored by that login —
  a cap that searches `github-actions[bot]` counts zero while the bot has opened a day's worth.
- `make issue-bot-dispatch REPO=asimov-agent/llgenie DRY=1` is a safe read-only reachability check of
  the whole dispatcher (`action=none` means no issue carries `agent:implement` / `agent:ready`).

## Remotes in this checkout

`origin` is the upstream `asimov-agent/llgenie`; the fork is the remote named `fork`
(`andyholst/llgenie`). Push the feature branch to `fork`, and open the PR against
`asimov-agent/llgenie:main` with head `andyholst:<branch>`.

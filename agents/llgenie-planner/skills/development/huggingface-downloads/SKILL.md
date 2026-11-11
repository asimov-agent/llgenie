---
name: huggingface-downloads
description: Use when downloading models/datasets from Hugging Face Hub.
version: 1.0
author: OWL
license: MIT
tags: [huggingface, model-download, cli]
---

# Hugging Face Hub downloads

Download models/datasets from the HF Hub to this user's machine, the way this user wants it done.

## When to Use
- Any request to download a model, GGUF, or dataset from huggingface.co (with or without the `hf` CLI named).
- Storing/renewing an HF token on this machine.

## Conventions
- Destination: `~/models/<RepoName>/` via `--local-dir`. Never scatter model files elsewhere in `~`.
- Tokens: a user-supplied HF token becomes an `export HF_TOKEN="..."` line in `~/.bashrc` (bottom exports section, alongside existing API keys). Never repeat token values in chat, notes, or skill files.

## Procedure
1. Recon first: fetch `https://huggingface.co/<repo_id>/tree/main` for the file list and target sizes. GGUF repos are often MANY quants (mradermacher, bartowski, unsloth ship 10-20 files at 2-7 GB each) — if so, ask the user which quant before downloading; never pull the whole repo or guess a quant. Use `--include "<exact-filename>.gguf"` to fetch only the chosen file.
2. Install CLI if `which hf` is empty: `uv tool install huggingface_hub` — installs `hf` and `huggingface-cli` into `~/.local/bin`. The `[cli]` extra no longer exists in hub 1.x; the plain package is enough.
3. Token: if new, append the export line to `~/.bashrc`, then ALSO export it inline in the download command — `.bashrc` edits do not propagate to already-running or non-interactive shells.
4. Download in background with notify=true (bounded task):
   `export HF_TOKEN="..."; ~/.local/bin/hf download <repo_id> --local-dir ~/models/<RepoName>`
   Use the full `~/.local/bin/hf` path to avoid stale-PATH issues in long-running terminal sessions.
5. Monitor by sampling the newest partial file:
   ```
   d=~/models/<RepoName>/.cache/huggingface/download
   f=$(ls -t $d/*.incomplete | head -1); s1=$(stat -c%s "$f"); sleep 30; s2=$(stat -c%s "$f")
   ```
   Poll file size instead of a blocking process wait — waits clamp to a few minutes, far shorter than a multi-GB transfer.
6. On completion the file moves to `<local-dir>/<filename>`; verify its size against the repo page, then optionally remove `<local-dir>/.cache/` to keep the dir lean.

## Pitfalls
- **A token on a Hub WEB PAGE buys you a 429; the same URL answers 200 without it.** `https://huggingface.co/<org>/<repo>` fetched with `Authorization: Bearer …` comes back `429 Too Many Requests` ("we had to rate limit your IP … make sure you pass a HF_TOKEN"), because a token-bearing web-page GET is accounted against the API quota. So an existence probe that authorizes every Hub URL marks live models dead while the identical probe without the token passes — verify by fetching the same URL twice, once with the header and once without, before blaming the link. Ask the API for existence instead (`https://huggingface.co/api/models/<org>/<repo>`, token attached: plain `200`/`404`), never send the token to a page, and treat any 429 as transient — wait the stated window and retry — rather than a verdict about the link. A ladder that retries only 5xx and calls every 4xx "dead at once" converts one throttle into reported data loss.
- **When validating that HF links exist, a 401 is NOT a dead link — it is a GATED repo.** A ranged GET (`Range: bytes=0-0`, `User-Agent: llgenie-test`) returning 200/206 means the file exists; 404 means genuinely dead; **401/403 means the file exists but the repo is gated** behind a token + license acceptance (e.g. `meta-llama/*`). When a link-validation probe reports failures, group them by repo and check the status code before declaring them dead — a whole repo answering 401 is gated, not broken, and the fix is a `HF_TOKEN`, not a catalog edit. Never report gated repos as dead links.
- A model is NOT one GGUF file. Large models (e.g. 100B+ quants) are sharded into `00001-of-0000N.gguf` parts, and some inference engines (Strata, and others) require ALL shards of a specific quant — the engine's own mapping logic decides which quant and how many shards. When a downloader is told to fetch a model for a chosen engine, match the engine's mapping (quant + shard count) instead of assuming a single file or guessing a quant. Multiple GGUF files downloading is normal, not a bug.
- Watch the NEWEST `*.incomplete` (`ls -t | head -1`), never an arbitrary glob/find order — restarted downloads leave orphaned partials, and a stale glob reads a dead orphan as a "stall".
- Confirm a real stall (newest partial's size AND mtime static across two spaced checks) before killing a download — hub 1.x names partials per attempt, so a restart starts from zero and discards the killed attempt's bytes. A false stall diagnosis wastes the whole download.
- After killing a download, delete the orphaned partials (`cd <dir>/.cache/huggingface/download && ls -t *.incomplete | tail -n +2 | xargs rm`) — they hold GBs.
- **An authenticated token is a QUOTA, not a pass.** `Authorization: Bearer <tok>` on `huggingface.co` calls grants ~1000 requests per 5-min fixed window (unanonymized ~500, the warn threshold drops lower when the quota is mostly spent — check the `ratelimit` / `RateLimit` response header to read remaining + reset). A 429 during a bulk run is almost always window exhaustion, not missing auth.
- **When a CI job fails with 429/5xx on the Hub, rule out missing-auth BEFORE blaming rate limit — and vice-versa.** Same commit + same secret where one job goes green and a sibling goes red = exhausted window, not a wiring hole. To prove the token actually travels through the test container, confirm the run mounts `-e HF_TOKEN` on `docker run` AND the caller calls the shared `authorize()` helper that attaches the Bearer header to every `huggingface.co` request.
- **Exponential backoff does NOT fix an exhausted rate window.** Retry sleeps (1s/2s/4s) are tuned for transient blips and fail once 429s arrive continuously; a hard retry budget is consumed fast. If all attempts return 429, the fix is to reduce request volume (on-disk cache so the run is cold only once) or wait out the window — not to lengthen retries.
- **A read-phase socket timeout is `TimeoutError`, not `URLError`.** A retry loop that catches only `urllib.error.HTTPError`/`URLError` lets one slow read escape as an uncaught traceback: `socket.timeout` is the builtin `TimeoutError` since Python 3.10, raised inside `http.client`/`ssl` *after* the connection is established, and `issubclass(TimeoutError, urllib.error.URLError)` is `False` (a connect-phase failure is the wrapped one; a read-phase stall is not). Catch `(urllib.error.URLError, TimeoutError)` in every Hub retry seam, and prove it against a REAL local server that accepts the connection and answers nothing — a monkeypatched `urlopen` raising `URLError` cannot show you this class of bug.
- If a xet-backed repo's transfer misbehaves, `HF_HUB_DISABLE_XET=1` forces the classic HTTP download path (both paths verified working).

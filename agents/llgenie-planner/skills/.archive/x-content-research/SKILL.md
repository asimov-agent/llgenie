---
name: x-content-research
description: "Use when you need X/Twitter without X API: lightbrd.com."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [twitter, x, research, mirror, lightbrd, social-media]
    related_skills: [xurl, grounded-citations]
---

# X Content Research (no API)

When you need X/Twitter content — what people are saying, benchmark posts,
announcements, opinions — but the `xurl` skill's X API access is not
configured (no developer app / OAuth), use the **lightbrd.com mirror**. It
returns real post text, author handle, timestamp, and engagement counts, and
works through `web_extract`.

The `xurl` skill is the API path (needs a paid X developer app + OAuth setup).
This skill is the no-auth fallback for read-only research.

## When to Use

Use when you need to search or read X/Twitter posts — what people are saying
about a topic, benchmark figures, announcements, opinions — and the `xurl`
skill's X API access is not configured. Reach for it over `web_search` when the
user wants real X signal (actual posts with authors and engagement) rather
than a secondary summary. Skip it when you only need a general web answer.

## The technique

Search posts:

```
https://lightbrd.com/search?f=tweets&q=QUERY
```

Read a single post:

```
https://lightbrd.com/<handle>/status/<id>
```

Fetch these URLs with `web_extract`. Search results come back as post text
with author, timestamp, and like/repost counts inline.

**Rank by engagement, not just presence.** lightbrd returns view counts and
like counts inline with each post. When the user asks "what people like" or
"what's trending," rank the results by those counts (views/likes) rather than
listing posts in search order — that's the popularity signal they're after.
The `f=tweets` filter (already in the URL) drops the user-results tab and keeps
only posts.

## Pitfalls

- **lightbrd.com is behind a Cloudflare "Just a moment" rendering challenge.**
  A raw `curl`/`urllib` fetch returns a ~6 KB challenge page with no posts.
  Only a **rendering** HTTP client (Firecrawl / `web_extract`, which the Hermes
  tool uses) passes. Any automation that scrapes the mirror must go through a
  rendered-fetch path or a pre-scraped HTML cache — never depend on a raw HTTP
  client bypassing the challenge. `web_extract` is the reliable way in.
- **Engine-name-only queries return nothing.** Searches like `freeToken engine
  moE small gpu` or bare engine names (FreeToken, TensorFold) come back "No
  items found" — the mirror does not index them as search terms. Query by
  **model + token/VRAM/hardware qualifier** (e.g. `rtx 3090 tokens per second
  qwen`), and treat engine names as optional post-hoc signals, not query terms.
- **Peak speeds are often workload-specific, not typical.** A standout figure
  (e.g. Qwen3.8-27B ~381 tok/s) can be a context-lookup/RAG-reproduction mode
  rather than general chat. Always label engine + mode/hardware and never
  present a peak as typical — note e.g. "~133 tok/s chat, up to 381 context-
  lookup."
- **Group searches by backend, and rank by interactions then t/s.** For a
  trending-list task, run a query group per backend (NVIDIA/CUDA, Apple/Metal,
  CPU) over a rolling window, then rank results by likes/loves + comments first
  and t/s second, capturing the specific model + engine each post tested. See
  `references/llm-benchmark-searches.md` for the verified per-backend query
  library.
- **CPU-only LLM benchmarks are genuinely sparse on X.** Most "CPU" signal
  lives in offload-capable engines (FreeToken, llama.cpp CPU) surfaced by the
  CUDA/backend queries. Keep the CPU category thin by nature; never pad it with
  fabricated or guessed figures.
- **Parse t/s ranges with `re.findall` + max, not `re.search`.** A value like
  `"35.5-43.7"` or `"67-71"` — `re.search` returns the FIRST number (35.5, 67),
  not the peak. When sorting a table by highest t/s, extract all numbers and
  take the max, or the sort silently mis-ranks.
- **Sort by the extracted t/s field, never by regex-scanning the whole row.**
  Scanning a rendered row for numbers picks up the year (2026) and date digits
  as the "max", breaking the sort. Compute the peak from the structured t/s
  field, then sort on that.
- **X.com itself is bot-walled.** `web_extract`/Firecrawl returns "Website Not
  Supported" for x.com URLs. Nitter instances (nitter.net, xcancel.com,
  nitter.poast.org, nitter.privacydev.net) are down, suspended, or blocked.
  Don't loop on them — go straight to lightbrd.com.
- **Search is noisy.** A broad query returns unrelated posts (ads, crypto,
  off-topic threads). Use specific quoted queries to cut through, e.g.
  `"tokens per second" local llm` or a model name + `benchmark`. Iterate on the
  query rather than paging through noise.
- **Results are truncated.** `web_extract` returns a head+tail window and saves
  the full page to a cache file (path in the result footer). Page through that
  file with `read_file` to see the omitted middle.
- **Community numbers are directional, not lab-grade.** t/s and benchmark
  figures in X posts are self-reported on unknown hardware. Label them
  "community-reported on X" and note the hardware each figure was measured on;
  don't present them as authoritative.
- **"What people like" means real post signal, not roundups.** When the user
  asks what's trending/popular on X, they want actual posts with authors,
  engagement, and hardware-specific figures — not a compiled blog roundup.
  Reach for lightbrd over `web_search` for this. And when they push for "more
    detail," they want it aggregated: full model/product names, source links,
    per-backend breakdown (e.g. CUDA/CPU/Metal), measured figures with the
    hardware each was run on, and the tool/engine to use. Deliver that shape
    up front rather than a summary they'll have to ask to expand.
  - **Aggregated lists have a strict sort shape.** For a "trending X" list the
    user wants: group by backend/GPU type first (CUDA, CPU, Metal), then by
    VRAM tier (6/8/12/16/24/32/48/64/96/128/256/384/512 GB), then sort each tier
    by highest t/s. Give **one** specific engine per model (llama.cpp, Ollama,
    vLLM, MLX, TensorFold, FreeToken) — not a list of options. Don't mention the
    user's own hardware in the deliverable unless they ask.
- **Don't republish one person's curation as your own.** When a user asks to
  collect "what X user Y likes," compile from the broader community's posts
  and attribute each item to its real source, or have the user paste the
  specific picks — don't lift a single profile's feed wholesale and strip the
  attribution.
- **Verify source links (HF, GitHub) before publishing a list.** Model/product
  IDs often differ from the marketing name — e.g. "Qwen3.8-Max" is the HF repo
  `Qwen/Qwen3.8-2.4T-A95B`, "Mach-1" is `SyzygyResearch/Mach-1-Additive-35B`.
  When a list carries links, `web_search` each one to confirm the real repo path
  rather than filling it from naming convention; a wrong link is a correction
  the user has to chase. Batch the lookups in one `execute_code` pass.

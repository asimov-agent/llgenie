---
name: agent-fetch
description: Use when a bot leg must fetch one URL with the masked Firecrawl key and write its text to a file — the key is read from the environment and never printed.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, web-reach, firecrawl]
---

# Masked web reach

A bot cannot verify what it cannot read. This is the repository's ONE sanctioned way to reach the
web: one URL in, its text out, the key never printed.

## Inputs

- `$URL` — the exact URL to fetch. Nothing else is fetched.
- `$OUT` — the path the fetched text is written to.
- `$FIRECRAWL_API_KEY` — the **name** of the environment variable that holds the key. Read its
  VALUE from the environment at call time.

## Output

The page's markdown, written to `$OUT`. Nothing else changes.

## Rules

- **The key never appears anywhere.** Not in the output, not in `$OUT`, not in a comment, not in a
  command you echo — it goes into one HTTP header and nowhere else. This run's transcript is
  redacted by the host, but a value you print has already left the process by then.
- **The request shape is fixed:** `POST https://api.firecrawl.dev/v1/scrape`, header
  `Authorization: Bearer <the key read from the environment>`, body
  `{"url":"<the URL>","formats":["markdown"]}`.
- **A refusal is loud, never a fallback.** On 401/402/403 print `HTTP <code> for the key` and exit
  non-zero: do not retry with another key, do not substitute a search engine, do not invent content.
- **An empty page is a failure, not a success** — say so rather than writing a file that records
  nothing.
- **Touch no file other than `$OUT`.** No branch, no commit, no push.

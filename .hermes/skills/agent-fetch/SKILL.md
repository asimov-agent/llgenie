---
name: agent-fetch
description: Fetch exactly one URL with the masked Firecrawl scrape API and write its markdown to OUT — the key is read from the environment by name and never printed, echoed or written anywhere.
---

# agent-fetch

One URL, one masked fetch, one output file. The host forwards the credential; the value must
never reach a log, a file or the console.

## Inputs

- `URL` — the single URL to fetch, given by the leg.
- `OUT` — the path the returned markdown is written to, given by the leg.
- `FIRECRAWL_API_KEY` — the **NAME** of the environment variable that holds the key. Read its
  VALUE from the environment.

## Output

- `OUT` at the repo root, containing the returned markdown — and nothing else.

## Rules

- Call the Firecrawl scrape API: `POST https://api.firecrawl.dev/v1/scrape` with header
  `Authorization: Bearer <the key's value>` and body
  `{"url":"<URL>","formats":["markdown"]}`.
- **Never print, echo, write or copy the key's value anywhere** — not in the output, not in
  `OUT`, not in a comment, not in a command line.
- If the API answers 401/402/403, say `HTTP <code> for the key` and exit non-zero. Do not retry
  with another key and do not invent content: a fetch that did not happen must read as a
  failure, never as an empty page.
- Touch no file other than `OUT`, do not create a branch, do not push.

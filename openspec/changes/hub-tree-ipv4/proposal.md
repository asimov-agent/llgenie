## Why

`macos / unit` on the #154 push to `main` failed
`test_download_mlx_repo_snapshot_for_real`: the Hub tree listing timed out,
`_tree` stored that as no files, and `plan_download` returned `None`. Linux
passed the same test. The macOS runner hangs on the IPv6 address of
`huggingface.co`, and the retry reused the timed-out request.

## What Changes

- Each Hub GET builds a new request and is opened over IPv4, falling back only
  when the host has no A record. Timeouts and 429/5xx are still retried.
- `_tree` does not cache a transport failure as an empty listing. An HTTP error
  for a missing repo still caches no files.
- Tests lock the retry and the IPv4 lookup.

## Impact

- `scripts/model_engine_pick.py`, `tests/test_trend_pick.py`, `README.md`

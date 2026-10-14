# Tasks

- [x] 1. `scripts/code_review.py`: the checks (inline scripts, undefined secrets, never-ran,
      cron collisions, reusable orphans), each emitting a key + title + evidence + where.
- [x] 2. The filer: one issue per NEW finding, marker dedup, cap per run, `--dry` preview; no code
      mutation of any kind.
- [x] 3. `make code-review-scan` / `make code-review-file` + `.PHONY` + `make help` + README, so the
      targets are reachable exactly as every other stage is.
- [x] 4. `.github/workflows/code-review-bot.yml`: guard before any secret, scan, file, weekly
      Monday 07:23 UTC + dispatch.
- [x] 5. `tests/test_code_review.py` wired into `test-unit`; the bot's own workflow passes the bot's
      own checks (cron slot included).
- [x] 6. Verify: the suite, `make check-wiring`, `make lint`, and a real `scan` against the live repo.
- [x] 7. File the findings the first real run produced as issues (the backlog the tree already had).

# Tasks — registry-link-check-hub

- [x] 1. `scripts/hf_auth.py`: `authorize()` attaches the token to Hub endpoints (`/api/…`, `/resolve/…`) and never to a Hub web page.
- [x] 2. `scripts/sync_registry.py`: `hub_api_url()` maps a `/<org>/<repo>` Hub model page to `/api/models/<org>/<repo>` and answers `None` for everything else; `check_links()` asks that URL and routes every link through `hf_auth.hub_open`.
- [x] 3. `tests/test_trend_pick.py`: the three new tests (API target + no token on a page, 429 waited out, authorize's header rule); the live link test and the 504/404 retry test keep passing.
- [x] 4. Proven red-first: with `origin/main`'s `sync_registry.py`/`hf_auth.py` the three new tests fail (`3 failed`); with the change they pass (`6 passed`).
- [x] 5. Measured on this host: `make check-registry` exits 0 on the committed 23-model store and on a freshly synced 106-model store (22.7s; the 18×429 run of #690 is gone).
- [x] 6. `agent-wiki/2026-10-26-registry-link-check-hub.md` + a `CHANGES.md` row name #690; `make check-docs` ok (no user-facing target or section changed).
- [x] 7. `make test-unit` green (`5234 passed, 6 deselected`, 678.82s) and `make openspec-validate NAME=registry-link-check-hub` exits 0.

# gates-makefile-split

## Why

The 2,083-line Makefile cannot be reviewed or maintained as one file: it piles the host / gate /
coverage surface (`bash-check`, `check-host-space`, `reclaim-tmp-worktrees`, every `check-*`,
`*-report`, the `git-identity-*`, `openspec-*`, `lint`, `lint-fix`) and its inline shell/python
recipes onto every other domain, so a change to any one target drags the whole monolith. The
big-bang split PR #2454 was closed by the owner because it changed too much at once; issue #800
demanded the decomposition — one domain per mergeable issue. This change is the gates-domain slice.

## What Changes

- New `mk/gates.mk` carries ONLY the gates-domain targets, byte-for-byte (names + recipes unchanged),
  with the top `Makefile` keeping the shared environment / `.PHONY` / `version` / `help` and adding
  `include mk/gates.mk`.
- Every Makefile-text reader resolves `include mk/*.mk` before reading targets, so no gate goes blind:
  `scripts/check_wiring.py` (`_makefile_list`), `scripts/check_docs.py` and
  `scripts/architecture_bot.py` (`_makefile_text`), `scripts/check_dispatch_forms.py`
  (`makefile_targets`), `scripts/issue_bot_gates.py` (`_makefile_text`), and `tests/conftest.py`
  (`makefiles_text`).
- Tests that sliced a moved gate target out of the top Makefile now read through the resolver.

Issue: [#2457](https://github.com/asimov-agent/llgenie/issues/2457) (decomposed from
[#800](https://github.com/asimov-agent/llgenie/issues/800), supersedes the closed big-bang #2454).

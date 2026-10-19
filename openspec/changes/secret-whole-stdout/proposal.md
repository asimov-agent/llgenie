# secret-whole-stdout — proposal

Issue: [#361](https://github.com/asimov-agent/llgenie/issues/361) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

`scripts/check_secret_output.py` is a fork of the sibling repo's guard and is **behind by three rule
families** — the ones that catch what a *bot pipeline* actually does. Both files carry the same rule
names and the same "a check with a name, so a failure says what to do" shape; llgenie's is 223 lines,
`trending-local-llms`' is 459.

Measured on `main@6338fc6`:

```
$ wc -l scripts/check_secret_output.py                            # 223
$ wc -l ../trending-local-llms/scripts/check_secret_output.py     # 459
$ grep -n 'github\|GITHUB_OUTPUT\|tee \|dev/stderr' scripts/check_secret_output.py
136:        is_workflow = rel.startswith(".github/workflows/")     # ← the only hit
```

Missing:

1. **`secrets-in-run-block` does not cover GitHub's own token.** llgenie has **12** uses of
   `${{ github.token }}` in its workflows; all sit in `env:` (the correct form) and nothing stops the
   thirteenth from being interpolated into a `run:` block, which leaks it into the script text, `ps`
   and any `--debug` output — the same credential under a different name.
2. **`whole-stdout-into-output-file`.** `cmd | … >> "$GITHUB_OUTPUT"` (or `$(cmd) >> "$GITHUB_OUTPUT"`)
   puts a command's WHOLE stdout in Actions' output file instead of `key=value`: `make` echoing its
   recipe line is enough to fail the step with `Invalid format` *after* it did the work, and every
   byte a target prints lands in the file. llgenie has five `>> "$GITHUB_OUTPUT"` writers, all in the
   safe `echo "k=$(…)"` form and none guarded.
3. **`whole-stdout-into-log`.** `… | tee /dev/stderr` copies the whole stream into the job log, where
   GitHub masks registered values only — a transformed one sails past. Nothing guards that shape
   today, and the redaction seam (#359) is about to make "print the stream" a deliberate act.

## What Changes

- **`scripts/check_secret_output.py`**: port the three rule families with the sibling's rule names and
  their place in the docstring (the failure message is the fix instruction). The pipe rule is
  tightened to a **single** `|` (lookarounds), because llgenie's workflows use `a || b` shell-or
  chains that end in `>> "$GITHUB_OUTPUT"` and a loose `|` flags them — measured while porting.
- **`tests/test_secret_output.py`**: one planted fixture per rule (and one *safe* counter-shape per
  rule: `env:`-passed `github.token`, the quoted `echo "k=$(…)"`, `tee /tmp/out.log`), so the guard
  cannot be loosened to green and the safe forms cannot start failing.
- **`README.md`**: the two new rows in the "No secret value reaches a log (#283)" table, and the
  widened `secrets-in-run-block` row.
- **`agent-wiki/2026-10-19-secret-whole-stdout.md`**: the work record.

## Impact

- The guard now catches the two shapes a bot pipeline produces when it publishes output, and GitHub's
  own token in a `run:` block.
- No behaviour changes for the tree as it stands: the current 12 `github.token` uses and 5 output
  writers are all in the safe forms, and the suite pins both the violation and the safe shape.
- Out of scope, filed separately: the value scanner (gitleaks) that reads a committed VALUE
  ([#360](https://github.com/asimov-agent/llgenie/issues/360)) and the redacted run log
  ([#359](https://github.com/asimov-agent/llgenie/issues/359)).

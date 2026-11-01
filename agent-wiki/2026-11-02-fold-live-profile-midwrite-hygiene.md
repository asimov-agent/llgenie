# process(fold-live-profile): neutral MID-WRITE reporting leg — issue #1323

## The defect

`scripts/fold-live-profile.py` line 96 printed
`MID-WRITE  {rel} -- live hash moved between two reads (another lane editing); re-read later`.
That parenthal ownership-guess ("another lane") carries no evidence sha, which is exactly the
blame-sentence the **report-hygiene guard** (#1292, `scripts/check_report_hygiene.py`) reds:
`make check-report-hygiene` / the `linux / unit` hygiene tests
(`test_whole_repo_is_green`, `test_exit_code_matters`) failed on every head carrying the tool
(verified run `41305723460` at head `3d088331`). #1317's clean PR was blocked by this ambient red.

## The fix (evidence-or-silence, neutrally)

Line 96 now reports the measured transient state without guessing an owner:

```
  MID-WRITE  {rel} -- live hash moved between two reads; re-read later
```

The MID-WRITE branch itself is untouched: the tool still reads live **twice** with a pause, still
appends the file to `midwrite[]`, still exits (and refuses a blind copy) on an unstable hash — only
the *attribution* changed. No fabricated lane, no fabricated sha. No fold behaviour change (byte
copy, drift/midwrite reporting, TH/TF reads, pause all identical).

## Proof at the head

- `make check-report-hygiene` rc 0: "no reporting leg blames ownership without a sha evidence anchor".
- `tests/test_check_report_hygiene.py` in `ghcr.io/asimov-agent/llgenie/test:5e0bae123ac9`: **9 passed**
  (incl. `test_whole_repo_is_green` and `test_exit_code_matters`).
- `check-wiring` green (tool already host-only via `tester-fold-live`); `py_compile` OK; sub-assert
  style: no test pins the exact wording (only line 96 itself references it, grep-confirmed).

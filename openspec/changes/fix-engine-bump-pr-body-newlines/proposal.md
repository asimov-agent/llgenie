# fix-engine-bump-pr-body-newlines — proposal

## Why

The engine-bump workflow's **Open / update the bump PR** step
(`.github/workflows/engine-bump.yml`) builds the PR body as a bash
double-quoted string that contains `\n` escape sequences. Inside a `.yml`
`run: |` block those bytes reach bash unchanged, and bash does **not** interpret
`\n` inside double quotes as a newline — it keeps the two characters backslash + n.
Result: every bump PR body renders literal `\n` text instead of line breaks, and
the backticks are likewise mangled by the `\`` escaping (see PRs #138–143).

## What Changes

- `.github/workflows/engine-bump.yml` — build the base body with
  `printf '…%s…'` (whose format string *does* interpret `\n` into real newlines),
  and append the hard-fail warning with `printf '%b'`. The
  `${{ github.repository }}` expression and matrix values continue to
  interpolate as before; the open-vs-edit PR decision and branch handling are
  unchanged.

## Impact

- No behaviour change to the pin/derive/apply/regen logic — only the rendering
  of the PR body.
- CI-parity: the generated shell still validates and runs under bash as before.

Issue: #144.

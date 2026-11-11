# Secret-exposure guards and redaction seams for bot CI

## OpenSpec task boxes must be tickable BEFORE the merge

`openspec-tasks-check` fails closed (red `ci-openspec`) on ANY `- [ ]` line in
`openspec/changes/<name>/tasks.md`, and a reviewer reads a ticked box as
verified evidence. Two consequences for the tasks list:

- **Every box is ticked in the SAME commit as the fixes that verify it** — the
  final "CI green" box is a closed loop (only true after the run passes, but the
  gate reads the file before you can tick it), so tick it together with the fix
  instead of letting it hold the branch red. Word each box with EXACTLY what you
  ran/verified, never a fuller claim; a false/exaggerated tick is worse than
  none.
- **No task box may be only-true-post-merge.** A final box like "dispatch the
  new job after merge and read its run" is untickable at review time, so it
  reds the gate forever and can never be a checklist item. Replace it with the
  verification you CAN read now (the scheduled/CI job that reads the secret IS
  the eventual live proof of the value), or drop it to a plain note below the
  checklist. The live end-to-end proof then belongs after the merge, not in
  `tasks.md`.

## The rules for `scripts/check_secret_output.py` and the redaction seam

The rules for `scripts/check_secret_output.py`-style guards and for the seam that
redacts a bot's transcript before it prints. Distilled for writing ANY of these
in this repo or a sibling, not a record of one change.

## Why the whole-stdout shapes are leak classes

GitHub masks only **registered** secret values in the job log. A transformed
value (URL-encoded, base64, a slice) or a whole copied stream sails past the
masker. A bot pipeline produces exactly those shapes when it publishes output:

- **Whole stdout into `$GITHUB_OUTPUT`** — `cmd | … >> "$GITHUB_OUTPUT"` or
  `$(cmd) >> "$GITHUB_OUTPUT"`. The file must hold `key=value` only, so `make`
  echoing its recipe line is enough to fail the step with `Invalid format`
  AFTER the work is done, and every byte the target prints lands in the file.
  The SAFE form is the quoted computed value `echo "k=$(…)" >> "$GITHUB_OUTPUT"`
  — keep it green.
- **Whole stream into the job log** — `… | tee /dev/stderr` (or `/dev/stdout`).
  `tee <file>` is fine; only the device targets copy into the masking-uncovered
  log.

## GitHub's own token is a secret too

`${{ github.token }}` interpolated **inside a `run:` block** is the same
credential as `secrets.GITHUB_TOKEN` — it becomes script text, shows in `ps`, in
`--debug` output and in the log. The safe form passes it through `env:`.
Match all three spellings: `github.token`, `github['token']`, `github["token"]`.

## Porting a pipeline rule: the single-`|` trap

When copying a rule that matches a pipeline (`cmd | …`) from a sibling repo,
the source's loose `|` over-matches the shell-or operator `a || b` that the
target repo's scripts use (a chain that ends in `>> "$GITHUB_OUTPUT"`). Tighten
to a single pipe with lookarounds (`(?<!\|)\|(?!\|)`) and RE-VERIFY against the
real tree: the port must be a strict improvement on the copy, and it must stay
green over the repo's own idioms — measured, not assumed.

## A redaction seam a leg's `exit` cannot skip

Wrap the leg's recipe in ONE make macro that runs the redactor in a subshell and
preserves the leg's exit status (`$(call scrubbed_run,…)`), so a leg that
`exit`s early still redacts its transcript before anything is copied to the
log or an upload artifact. A seam bolted on afterwards (a redactor that runs
only on the happy path) is not a seam.

## Every rule is pinned both directions

One violating fixture AND one safe counter-shape per rule (the `env:`-passed
`github.token`, the quoted computed writer, `tee /tmp/out.log`), so the rule
cannot be loosened to green and the safe forms cannot start failing. A tree-wide
check (`check-secret-output` over the whole repo) proves the repo itself is
clean under the new rules.

## A leg's credential must be set on the STEP that runs it, not a sibling

A make leg forwards credentials into the agent image with `-e KEY`. The workflow
STEP that actually invokes that leg must export each forwarded key (job-level
`env:` or the step's own `env:`) — a SIBLING step's `env:` does NOT count. This
is the exact shape of the bug where the dispatch step and the later push/PR steps
export `GH_TOKEN` but the implementer's step does not: the container gets an
EMPTY value and every `gh` call inside the leg runs unauthenticated while the
log reads as correctly wired.

Enforce it as a RULE, not a one-off: the test derives the roster of forwarded
keys from the Makefile (grep the `-e NAME` list), then for each bot workflow
resolves the step that runs the leg and fails when that step cannot see a key.
A new `-e KEY` on a leg whose workflow step does not export it then fails the
suite instead of shipping an empty value.

## Prove the fix against the ACTUAL defect, not a fixture

To show a detector is real (not a loosened test), read the PRE-fix content from
`git show HEAD:<file>` and run it through the SAME functions the suite uses, so
the detector is proven against the real defect; then run it on the current file
for the post-fix value. Print both (`pre-fix step sees GH_TOKEN: False` /
`post-fix True`) in the PR. Keep a synthetic fixture too, so the shape is pinned
independently of the repo's current state.

## A missing-key guard is name-only and runs BEFORE the image pull

A loud missing-key guard (`scripts/require_env.py`) checks each required name
and exits non-zero on a missing OR empty value, and refuses names that are not
on the allowlist (so a typo cannot silently pass). It is the FIRST recipe line
of every agent leg, ahead of the image pull, so a leg fails fast with a clear
message instead of pulling an image and then failing inside the container. The
roster is derived from the Makefile so the guard and the suite cannot drift.

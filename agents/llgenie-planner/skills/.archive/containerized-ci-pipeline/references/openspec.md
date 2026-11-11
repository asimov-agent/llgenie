# OpenSpec change workflow (llgenie)

Durable rules for driving an OpenSpec change through `make openspec-*` in the
llgenie repo. These are the pitfalls that cost time; the repo's AGENTS.md owns
the mandatory workflow (change-first, issue→branch→change→code→PR, sync-back).

## Validate requires a delta header

`make openspec-validate NAME=<change>` exits 2 with "No delta sections found" /
"Change must have at least one delta" when a `specs/<cap>/spec.md` opens its
requirements under a bare `# <cap>` heading and goes straight to
`### Requirement:` blocks. The validator only counts requirements under a delta
header — `## ADDED` / `## MODIFIED` / `## REMOVED Requirements`. Write the delta
header when you scaffold the spec, not after the first red validate.

## The change dir is root-owned after `make openspec-new`

The `openspec` container runs as root and writes `openspec/changes/<name>/`
(and any scaffold) as root, so the very next `write_file`/`patch` into
`proposal.md`/`spec.md`/`tasks.md` dies with `Permission denied`. Fix
immediately after `make openspec-new`: `sudo chown -R <user> openspec/changes/<name>/`,
then edit normally. Do this before writing any change file.

## Last task must be verifiable NOW, not "CI green"

An `openspec-tasks-check` job walks every active `openspec/changes/*/tasks.md`
and fails unless ALL its `- [ ]` tasks are ticked. A final acceptance task
worded "CI green on this PR" can never be ticked while the job is red
(chicken-and-egg). Write the last task as something verifiable immediately
("issue, change and code agree; PR references the issue"), tick it as soon as
verified, and run `make openspec-tasks-check` + `make openspec-validate`
locally before pushing.

## Validate is the gate, not the whole loop

When the user asks to skip a stage (e.g. "skip make test-unit"), still run
`make openspec-validate` and tick its task before squashing — the validate gate
is cheap and independent of the skipped test stage.

## A spec `- **Test:**` reference must name a REAL function

The `- **Test:** \`tests/file.py::func\`` line is the reviewer's jump point; a `func` that does
not exist (or is guessed) is as dead as a missing line. The real test is often NESTED inside a
large file-level function — a suite wires many scenarios as `def test_issue_bot():` with dozens of
assert blocks, each labelled by a helper message, not by its own `def`. Before naming a `::func`,
grep the file for the actual `^def test_` and cite the enclosing one, or the reviewer lands on a
function that isn't there.

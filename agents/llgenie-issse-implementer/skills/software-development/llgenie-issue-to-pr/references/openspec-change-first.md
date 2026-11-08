# OpenSpec change-first: every code change carries its own change dir

## The rule
Every code change in the repo must be accompanied by an OpenSpec change under
`openspec/changes/<name>/`. AGENTS.md makes this mandatory and *change-first*
(write the change with the code, not after). An implementer PR that touches code
but adds no `openspec/` file is "openspec-empty" and is a legitimate
`do-not-merge` whose remedy is exactly "carry your own OpenSpec change".

## CI validates but does NOT enforce presence
`linux / openspec` runs `make ci-openspec`, which validates every active change
and exits 0. On an openspec-empty PR it passes because there is nothing to
validate — absence is not a red. So a green `linux / openspec` is NOT proof your
PR carries a change: verify the directory exists in the head tree yourself with
`git ls-tree -r <head> -- openspec/changes/<name>/`. The gate that reds an
The gate that reds an implementing PR for a missing/unnamed openspec change is the
`guard` job step `make check-pr-openspec-change` (implemented by
`scripts/check_pr_hygiene.py openspec-change`). Reproduce it locally BEFORE pushing:
commit the openspec dir first (the script reads the COMMITTED head tree — staged-only
still reds), then run
`python3 scripts/check_pr_hygiene.py openspec-change --head "$(git rev-parse HEAD)" --base "$(git merge-base HEAD <base>)" --body-file /tmp/prbody.md`
where `/tmp/prbody.md` is the LIVE body: `gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/prbody.md`.
It passes when the committed diff adds a file under `openspec/changes/` OR the body
carries an `OPENSPEC: <name>` line. Two traps: an empty `--body-file ""` is read as
`.` and raises `IsADirectoryError`; and running it against the pre-commit head when the
files are only staged reports the same "adds no file under openspec/changes/" red.
When an ALREADY-OPEN PR reds this step, add the change dir and push to the SAME branch
(no second vehicle); the guard then re-runs on the new push.

## Scaffold then AUTHOR the files
`make openspec-new NAME=<name>` (dockerised `openspec` scaffold) creates only
`.openspec.yaml`. The name is a MAKE VARIABLE, not a positional argument: a bare
`make openspec-new my-change` runs the target with `NAME` empty and scaffolds nothing,
which reads as a scaffold that silently did nothing. You must author the real content:
- `openspec/changes/<name>/proposal.md` — why + what changes
- `openspec/changes/<name>/tasks.md` — checklist, all `- [x]` when done
- `openspec/changes/<name>/specs/<name>/spec.md` — the requirement delta
Validate before pushing with the DIRECT target `make openspec-validate NAME=<name>`
(rc=0) and `make openspec-tasks-check` (all tasks OK). Do NOT rely on `make ci-openspec`
or `make ci-lint` as in-worktree proof: they shell out to nested docker-in-docker and a
linked worktree mount fails them with `Cannot connect to the Docker daemon` / the
check-docs census sub-step reads `.git` as UNREADABLE ("run this from a full clone").
That is an environment artifact of the worktree, not a regression — the direct
targets are authoritative. Re-add trailing newlines (write_file drops them) so
check-docs stays green.

## What counts as "code" for the gate (docs-only is narrower than it looks)

A workflow / `.github/workflows/*.yml` edit is **NOT docs-only** — it is a product change for
the openspec gate, exactly like a `.py` edit. The `_is_docs_only` allowlist covers markdown/docs
paths only. So a "just tweak one YAML key" PR still needs a `openspec/changes/<name>/` dir (or a
body `OPENSPEC:` line); without one it reds the change gate. Same for config/params files.

## The spec needs a `#### Scenario:` per requirement

`make openspec-validate` reds a `spec.md` whose requirement has no scenario block. Each
`### Requirement:` needs at least one `#### Scenario:` (Given/When/Then prose) under it. Validate
BEFORE pushing, not after the CI red.

## `openspec-validate` checks STRUCTURE, not correspondence — re-sync the spec on a mid-session revision

`openspec validate` only proves a change is well-formed (requirement + scenario shape, task boxes).
It does NOT check that `spec.md` still describes what the delivered artifact actually contains. So
after ANY mid-session edit to the implementation (adding a row to a reference's decision/map list,
renaming a file stem, adding a directive), re-read `spec.md` and bring its parallel enumeration into
agreement in the SAME push — a spec that omits a rule the reference now ships is silent drift the CLI
passes green. Concretely: when you extend a delivered `references/*.md` gate→defect map with a new
entry, mirror that entry into the `spec.md` scenario's map list and re-run `make openspec-validate` +
`make openspec-tasks-check` at the new committed head.

`tasks.md` must name CONCRETE stems, never a literal `<date>` placeholder: write
`agent-wiki/<real-date>-<real-stem>.md`, not `agent-wiki/<date>-<slug>.md`. A placeholder still
passes `openspec-tasks-check` (it only counts `- [x]`) but misleads the next reader about what the
change actually shipped.

## Docs trio: the CHANGES.d fragment is EXACTLY ONE table row

A non-trivial change carries three docs artifacts (the #1123 trio): an `agent-wiki/<date>-<stem>.md`
**narrative** note, a `docs/changes.d/<date>-<stem>.md` fragment that is **exactly one table row**
(`| date | note | [agent-wiki link](...) | #N |`) — NOT a narrative paragraph — and the
regenerated `CHANGES.md` (`python3 scripts/changes_index.py write`, see
`mechanical-index-regeneration.md`). A multi-line or narrative fragment breaks the index render;
first authoring attempt as prose is the common mistake.

## Docker scaffold writes as root — chown it, OR write through a root container
A dockerised scaffold/validate writes files owned by root; the next `write_file`
into the change dir fails `Permission denied`. If sudo is passwordless,
`sudo chown -R $(id -u):$(id -g) openspec/changes/<name>` fixes it.

If sudo PROMPTS for a password (many hosts have no passwordless sudo), do NOT try
to pipe one and do NOT conclude you are blocked. Write the files THROUGH a root
container instead — it needs no sudo. Author them in a scratch dir, then
`docker run --rm -u root -v "$PWD":/repo -w /repo llgenie/test:latest bash -c 'cp <files> /repo/openspec/changes/<name>/'`,
chowning back to your uid in the same container (`-c '… && chown -R 1000:1000 /repo/openspec/changes/<name>'`)
so a later host `git add`/`write_file` still works. Use the `llgenie/test` image
(python+bash); the `openspec` image's entrypoint is `node`, so it needs
`--entrypoint bash`. Note: deleting a root-owned dir needs write on its PARENT
(`openspec/changes/`), not the dir itself — check the parent's perms before
assuming you are blocked.

## Clear the do-not-merge yourself when its remedy lands
A `do-not-merge` placed for openspec-empty is removable once the change is in
the branch and CI validates it: amend/push the change, then
`gh pr edit <n> --repo <o>/<r> --remove-label do-not-merge`, and re-run the
`holds` check (the failed run predates the removal). Confirm `check-holds` reads
0 held PRs and `gh pr checks <n>` shows `holds pass` before reporting green.

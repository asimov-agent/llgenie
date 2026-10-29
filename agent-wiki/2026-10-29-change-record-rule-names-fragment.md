# The change-record rule names the fragment, and a gate keeps it that way

Implements #942 (follows #934). Branch `docs/942-change-record`, measured on
`main@7db4ac99` (AGENTS.md 88587 b / 1323 l).

## What was verified

`make check-docs` had no opinion about the rule *text*, only about the record *shape*: a note with
no `docs/changes.d/<stem>.md` row is red, but a document that tells a contributor to append its row
to `CHANGES.md` was read as fine. So `main` carried the shape #934 built and, in the same tree, the
rule that produced the pile-up it removed — measured with
`grep -rn 'CHANGES.md' AGENTS.md docs/*.md` at `7db4ac99`:

| Path | Rule statement at `7db4ac99` | State after this change |
|---|---|---|
| `AGENTS.md:1029-1031` | "indexed in `CHANGES.md` in the SAME commit" | unchanged — **protected file**, recorded exception, see below |
| `AGENTS.md:1045-1047` | "**`CHANGES.md` — the index.** Add one row per change …" | unchanged — same exception |
| `AGENTS.md:1059-1060` | "when a note is missing from `CHANGES.md`" | unchanged — same exception |
| `docs/ARCHITECTURE.md:1171` | "its row in `CHANGES.md` (newest first)" | rewritten: own row under `docs/changes.d/`, `CHANGES.md` rendered by `make changes-index` |
| `docs/BOTS.md:9` | "indexed by `CHANGES.md`" | rewritten: own row under `docs/changes.d/`, rendered into `CHANGES.md` |

`agents/*/SOUL.md` states none of it: there is no `agents/` tree on `main@7db4ac99`
(`git ls-tree -d --name-only 7db4ac99` lists `.github .hermes agent-wiki containers data
docker-compose-files docs openspec scripts skills tests tools tools` — no `agents`), so the sweep
covered the files that exist.

## The gate (behaviour, not prose)

`scripts/check_docs.py` now reads every file that states the change-record rule
(`AGENTS.md`, `README.md`, `docs/*.md`, `agents/*/SOUL.md` when present) and fails when a mention of
`CHANGES.md` sits within 160 characters of both an append verb and a row/entry/line noun, unless the
same window names the mechanism (`docs/changes.d`, `changes-index`, "rendered"). A window that
corrects itself in the same breath passes; an instruction to append does not.

The exemption for the protected `AGENTS.md` is `APPEND_POINT_EXCEPTIONS` — path, issue, decided date
and a reason — and it is **falsifiable in both directions**: while `AGENTS.md` still names the
append, the entry is reported and the gate passes; the moment the file stops naming it, the entry is
STALE and `make check-docs` reds until it is deleted in the same commit that fixes the wording. An
exemption that outlives its reason is a failure, not a permission.

`tests/test_check_docs.py` proves the behaviour on a real scratch checkout: a `docs/RULES.md` saying
"Every change appends its row to `CHANGES.md`" exits 1 through the real CLI and names
`docs/changes.d/<note-stem>.md` and `make changes-index`; the same page rewritten to the fragment
shape exits 0; a clean page that still carries an exemption is STALE.

## Open, and why

`AGENTS.md` is a protected agent-instruction file: the write is refused without an owner-approved
prompt, and the refusal is explicit ("do NOT retry, or attempt the same edit via another path"). The
wording update is therefore filed as the remaining half of #942 and cannot land from this lane. The
exact patch is on the issue; the exception entry is removed in the same commit that applies it.

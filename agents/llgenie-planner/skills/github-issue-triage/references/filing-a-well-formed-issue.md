# Filing or restating an issue body that survives a shape gate

A repo that gates issue bodies (a renderer module plus a check target, e.g. `scripts/issue_body.py` and
`make check-issue-bodies`) turns "file an issue" into a formatting task with three traps that each cost a rewrite.

## 1. Use the repo's renderer, not your own section order

The canonical order is `Problem`, `Why it matters`, `How we fix it`, `Benefit`, `Acceptance criteria`, optional
`Not covered`, then `Technical` **last and only there**. Read the renderer's docstring before writing; it states the
mapping to the PR body (`Problem`↔`Issue:`, `How we fix it`↔`Fix:`, `Benefit`↔`Benefit:`, `Technical`↔`Technical:`),
and the gate frequently checks that the *producers* call it — a hand-built body is the defect, not just a shape miss.

Prose rules the renderers encode and a reviewer checks:

- `Problem` is the measured symptom with a number, not the ticket title.
- `How we fix it` is numbered plain language with **no file paths**; paths belong in `Technical`.
- Each acceptance criterion is one `- [ ]` line a reviewer can tick by running something.
- An optional deferral section names the owning issue per deferred item; without an owner it is just prose.

## 2. Demote `##` headings inside any pasted document

Embedding a file (a `SOUL.md`, a skill, a previous issue) inside a fenced block still leaks its markdown headings into
the body's heading scan: a pasted `## Standing behaviour` shows up as a top-level section *after* `Technical` and
breaks the "Technical last" rule for any regex-based check or reader.

```python
block = "\n".join(l if not l.startswith("## ") else "### " + l[3:] for l in pasted.splitlines())
```

`###` cannot match a `^##\s+` scan, so demoting is enough; do not strip the headings — the pasted text has to stay
verbatim to be the seed someone commits.

## 3. Write the body from a Python dict, never from a shell heredoc or an escaped f-string

- `gh api -X POST repos/<o>/<r>/issues --input -` with `json.dumps({...})` avoids every shell-quoting trap
  (backticks, `$(...)`, parentheses).
- Backslash-escaping backticks inside an f-string lands **literal backslashes** in the body (``\`make target\` ``);
  build the text without escapes and let JSON handle it.
- Post the body, then **read it back**: `gh issue view <n> --json body --jq .body`, re-run the section regex
  (`re.findall(r'^## (.+)$', body, re.M)`), and compare a pasted block against its source file. Fix with
  `gh api -X PATCH repos/<o>/<r>/issues/<n> --input -` and read back again.

## 4. You do not know the number until after the POST

A body that cross-references itself ("issue #N is tracking this") cannot carry the right number while it is being
drafted — a guessed number points at somebody else's issue. Either omit the self-reference and add it in a follow-up
comment, or POST, take `.number` from the response, and PATCH the body with the real one. Then grep the body for the
number you actually got: `"#<n>" in body` — and for any number you typed from memory.

## 5. Prove the write

A successful POST is not a filed issue: re-`GET` it and assert title, labels and section order, and for a label
change `gh api …/issues/<n> --jq '.labels[].name'` (a `--jq` on a POST response can error while the write succeeded).

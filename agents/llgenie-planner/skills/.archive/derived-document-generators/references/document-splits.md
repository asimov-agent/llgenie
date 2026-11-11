# Splitting one bloated document: user guide + reference pages + a change index

Use when a document (usually `README.md`) has become the union of every landed change —
issue-numbered sections, bot/CI internals, secret plumbing — and the request is "make it the
user doc, put the change history somewhere referenced".

## Procedure

1. **Classify every section by audience, not by size.** Three buckets: *user* (install, run,
   configure, layout, environment), *reference* (engine internals, bot/CI behaviour, contributor
   rules), and *history* (anything headed with an issue number or "what changed"). Only the raw
   text you already have is being redistributed — you are not writing new documentation.
2. **Cut mechanically, then edit.** Parse headings OUTSIDE code fences (a `# comment` inside a
   `bash` fence is not a heading — a naive `line.startswith('#')` split mangles code blocks),
   slice by heading ranges, and assemble the new files. Hand-write only the new head (what the
   project is + a table of which document answers what) and the joins.
3. **Give each kind of text exactly one home** and link them from the guide's first screen: the
   guide links the code map, the reference page, and the change index.
4. **Move every WRITER, not just the text.** Grep the tree for the old filename before you
   commit: a generator that renders a block into it (a dispatch/capability table), a bot that
   rewrites pins in it (engine bumps), a workflow step that `git add`s it. Each one must be
   repointed at the new home — otherwise the first scheduled bot re-grows the file you just
   cleaned.
5. **Make the rule a gate, and make the gate fail on the OLD shape.** The validator should fail
   when the guide carries an issue-numbered heading, a change-log heading, or the generated
   block's marker, when an index row points at a note that does not exist, and when a note exists
   that the index does not list. Prove each with a real scratch tree (a real Makefile + README +
   index + note files), not with a stub.
6. **Generate the index from the notes themselves** (date, title, link, issue/PR extracted from
   each note), then de-duplicate the date out of the rendered title (`| 2026-01-02 | 2026-01-02 —
   …` reads badly).
7. **Re-run the gate after every rebase.** The index is generated from a snapshot; a note that
   lands on the base while the change is open makes the gate red — add the row, keep the gate.

## Pitfalls

- **Tests read the old file by PATH, so moving text breaks them silently until CI.** Grep the
  test tree for the document's filename before moving anything: assertions like
  `assert "<target>" in README` and prose assertions (`"fewer LLM calls" in readme`) red the
  suite for a reason that has nothing to do with the change. Update them to the documentation
  SURFACE (guide + the linked reference pages), not to a different hardcoded path — then a
  target documented in either place passes.
- **A whole-file replacement conflicts on every rebase.** Resolve by taking your version
  (`git checkout --theirs` during a rebase of your own commit), then REPLAY the base's post-fork
  edits: `git diff <old-base> origin/main -- <old-path>` gives the exact hunks (a bumped
  version string, a new paragraph) — transplant each into whichever new file now owns that
  content. Skipping this ships moved reference text older than the base.
- **The index gate catches base drift; treat the failure as the mechanism working.** A new note
  merged on the base after you generated the index fails `check-docs` with "note is not indexed"
  — add the row and say so; do not loosen the check.
- **A documentation surface that spans files must be defined ONCE.** The validator concatenates
  the guide plus every `docs/*.md` the guide links; both the renderer and the validator call the
  same function, and a docs page the guide does not link documents nothing (a deliberate
  control: linking is what makes a page part of the surface).
- **A generated table's marker is a bot-write fingerprint.** Keeping the marker in the user guide
  means a workflow edit edits the guide; move the block (markers included) to the reference page
  and have the validator read it there.

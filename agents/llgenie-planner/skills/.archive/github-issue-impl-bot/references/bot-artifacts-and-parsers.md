# Bot artifacts and parsers

Three shapes that produce a GREEN run over a WRONG artifact. Each rule is imperative and
stands on its own; the mechanism is the clause after the dash.

## One producer, one reader — a `key=value` line, never a sliced row

Two consumers reading one producer's output with two hand-rolled shell parsers is a defect
waiting for a value that contains a space.

- **The producer prints the exact line the consumer needs** (`issue=<n>`, or `issue=` for
  nothing) and puts its reasoning on STDERR — then the consumer copies a value instead of
  re-deriving it. A positional `sed` over the producer's row is a second implementation of a
  contract the producer already owns, and only one of the two is usually tested.
- **Every value is a TOKEN.** The producer REFUSES a value carrying whitespace (or outside
  the shape): exit non-zero, name the key and the raw value. A consumer that then takes the
  value WHOLE is correct by construction; `awk '{print $1}'` never is.
- **Refuse loudly beats truncate silently.** A truncated `issue=` spends a whole implementer
  run on the wrong number, and any numeric guard AFTER the slice validates the already
  truncated value — so the run is green and wrong. A refused pick costs seconds.
- **Test each consumer against the REAL producer's stdout**, stubbing only the external CLI
  (a `make` that `cat`s the producer's captured output). Assert the pre-fix shape is
  REFUSED, not re-read: a parser whose only fixtures are its own has no test of the contract.

## `make` echoes its recipe into any redirected file — silence content recipes with `@`

`make <target> > file` writes the echoed command line as the file's FIRST line.

- A recipe whose output is redirected into a NON-log file must start its command lines with
  `@`. `*.log` captures are exempt: they are scrubbed streams, and one echoed command
  survives a redacted tail.
- The damage is only visible where the file is CONSUMED: an agent reading it as a
  specification opens with a command line, and a PR body GitHub parses for the closing
  keyword carries it too.
- **Guard it derived from the tree, not from a list:** collect every `make <target> … > file`
  the workflows perform (skip `*.log`, `$GITHUB_OUTPUT`, `|` pipelines, and `->` arrows in
  prose), then assert every command line of that target's recipe is silenced. Make the guard
  non-vacuous (it must find redirects) and name the measured case.
- **Prove it RED by restoring the base file**: swap in `git show origin/<base>:Makefile`,
  run the case, confirm the failure names the unsilenced recipe, restore.

## A generated file conflicts on every merge — regenerate it, then COMMIT it

A generated index/doc rewritten by every change conflicts on any rebase or merge, and
merging the base brings the BASE's copy back over your regeneration. That is the normal
state: **every merge re-stales every open PR's generated file** — do not debug it, repair it.

- Repair order: **merge the base → run the generator → `git add` → commit with an EXPLICIT
  message.**
- **Never `git commit --no-edit` there.** After a merge git auto-committed there is no merge
  message to reuse; the commit ABORTS (`Aborting commit due to empty commit message`) and the
  following `git push` ships the pre-regeneration file while the fix sits staged in the
  worktree.
- **Verify the PUSHED commit, not the worktree:** `git show HEAD:<file>`. `git status` and the
  file on disk are exactly what mislead here — they show the repaired content that never left
  the machine.
- A green PR whose `auto-merge` job fails with `GraphQL: Pull Request has merge conflicts` is
  this shape: the checks passed on an older base, and the generated file now conflicts. Nothing
  is wrong with the change; merge the base, regenerate, push.

## Pointers that cost a round

- A guard that asserts the SHIPPED YAML TEXT of a fix (`"if: steps.pick.outputs.x == ''" in
  step`) pins the defect: it goes green on the bug and red when the bug is fixed. Assert the
  INVARIANT ("the step is not gated on the pick") so the shape can change without deleting the
  guard.
- A guard that finds its target by slicing a fixed window after a marker string breaks when the
  marker also appears in a comment above the code. Assert inside the concrete command/recipe.
- When a new guard's first run against the REAL tree flags entries nobody classified, fold them
  into the manifest — that is the guard earning its keep, not over-strictness.

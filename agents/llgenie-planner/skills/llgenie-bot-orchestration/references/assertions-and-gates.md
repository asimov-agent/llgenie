# Assertions, shape changes, and gates that actually fire

Depth for the "assert behaviour, not text" rule. Every item here is a defect that shipped green, or was caught one
message before it did.

## A shape change has a spelling — grep the suite for it before you push

When a change replaces a construct (an inline command becomes a make target, a status field gains a new meaning, a group
is deleted), some test asserts the **old spelling**. CI reds on a fix that is correct, and the red looks like the fix's
fault.

```bash
# after changing a shape, before the first push
grep -rn "<old construct>" tests/ | head -30     # e.g. "python3 scripts/<x>.py", "callers[\"macos\"]", ".PHONY"
```

Then pin the **wiring** rather than the spelling: assert the make target is invoked, its arguments are passed, the old
inline form is *absent*, and the recipe still calls the script (so the decision stays covered end to end). A test that
asserts a literal command line reds on every behaviour-preserving refactor — the same failure mode as a test that pins
one spelling of a shell fallback (`${{ github.base_ref || 'main' }}` vs `${EVENT_BASE_REF:-main}`).

## Never assert a list the tree is meant to extend

Manifests, rosters, workflow sets and job lists grow. Equality reds on the next legitimate addition and teaches the next
person to edit the test:

```python
assert {"a", "b"} <= set(names)          # subset — the rule
assert set(names) == {"a", "b"}          # snapshot — reds when c joins
```

Keep the rule *and* the referents: subset membership plus "every listed name resolves to something real" (a directory,
a file, a live workflow). Subset alone lets a typo through, because `{"a","b"} <= {"a","typo","b"}` passes.

## Assert against the entry point that runs in production

A library and its CLI can disagree, and the CLI's correctness hides the library's failure — both are "the classifier"
to a reader, only one is right. When a decision lives in a wrapper (`main()`) rather than in the function (`scope()`),
the fail-safe branch exists at exactly one call site:

- measure expectations through the entry point the workflow invokes, and **name that entry point next to every table
  row** — otherwise two lanes measure 22 and 3 and both are "right";
- when a fail-open widening lives in the wrapper, move it into the function so the safe answer is the default, and flip
the test that documented the divergence into one that forbids it.

## A gate must fire on the PR that introduces it

Before trusting a new gate, run it against the change that adds it. A predicate that classifies *who* the change is for
can silently exclude the change itself:

```python
is_bot_pr = all(author == BOT_EMAIL for author in authors)   # one human commit → False → gate skipped
is_bot_pr = any(author == BOT_EMAIL for author in authors)   # errs toward enforcement
```

A real branch almost always contains a human commit (a rebase, an owner fixup), so `all(...)` makes the gate skip the
majority case. Encode the decision as **`any(...)`, or `all(...)` plus a notice naming the human commits**, and prove it
with a negative control executed on that branch.

## A check that cannot compare must say so

When a guard's second side is absent — no live profile on a CI runner, no credentials, no fixture — do **not** return silently. Silence makes "compared and fine" indistinguishable from "could not compare", and that ambiguity is how a truncated copy ships green.

```python
if live_home is None:
    print(f"[check] live comparison SKIPPED: no profile home at {path} — tree checks only")
    return 0
```

Skip (never fail) when the missing side is something the environment cannot supply — a runner that reds for a condition it cannot fix is an unfixable red — but make the skip a stated outcome, and assert the line appears so it cannot degrade back to silence.

## Symmetric gates

Every gate needs the negative control **in both directions**, or it is decoration:

| gate | must red when | must stay green when |
|---|---|---|
| trigger list equals class list | a path is added to one side | both sides are edited together |
| no inline script in a workflow | the inline form returns | the make target is used |
| no draft PRs | a draft is created | a ready PR is opened |
| no hung job | a job exceeds its ceiling | a job runs long but inside it |
| live profile covers tree copy | the tree file is shorter than the live one | both are byte-identical |

Run the red direction by *making* the defect (add the entry back, drop the bullet, shorten the file), watch it fail,
restore, watch it pass. A gate proven only by passing runs has never been seen to work.

## A sync/import direction has a dangerous side

When a repo copy mirrors a live artefact, the risk is asymmetric: a **tree copy shorter than the live file** means a
sync would silently replace a working rulebook with a fraction of itself, with a green gate — while a tree copy longer
than a stub is merely unsynced. Compare byte counts against the live artefact before any sync, refuse to shrink without
an explicit force flag, and make the length relation an assertion rather than a convention.

**The lie to design out: a sync verifies the copy, not the content.** A tool that writes tree → live and then reads
back what it wrote prints `verified: 3 file(s) read back identical` and exits 0 while the destination **shrank**,
because "identical" only meant "what I wrote matches what I copied". Rules disappear under a green, verified, successful
run. Three consequences for the guard and its tests:

- **Read the live size at sync time**, never against a captured number — the live file can change between measuring it
  and running the guard, so a stored byte count is stale on arrival.
- **Never print the word "identical" for a file whose size changed**: `verified: 3 copied, 1 shrank (7,509 → 5,149 b)`.
- **Pin the message, not just the exit code.** A refusal that still prints "verified" is the same lie with a non-zero
  status: assert the non-zero exit, both sizes present in the output, the shrink named, and `"verified" not in out` on
  the refusing path. **Compute the expected sizes from the fixture**, never as literals — a literal goes stale the moment
  the file changes, and the live file can grow between measuring it and committing. Add the mirror test for the success
  path too (`copied … replaced an existing file`, never `identical`): the refusal half alone leaves the misleading
  sentence alive on the path production actually runs.

Prove the whole thing on a **sandbox copy** of the destination (`cp -a` the profile or corpus, run the real target
against it, then check string presence for three rules that must survive). Reproduction on a copy is what turns "this
could delete rules" into a merge blocker nobody argues with — inference gets a discussion, a sandbox transcript gets a
fix.

## Anchoring a regex at end-of-line skips lines that carry trailing comments

A mechanical rewrite that matches `^import x$` never sees `import x  # noqa: E402`. Order the passes so scaffolding
goes first:

1. strip the trailing-comment scaffolding (`# noqa`, `# type: ignore`),
2. rewrite the construct,
3. then remove the line the construct needed (a path insert, a shim).

Otherwise the rewrite silently drops the import and leaves the path entry gone — a module-not-found on files you did not
sample. Prove any regex-driven migration by importing every file it touched, not a sample of five.

## An exemption is debt, not amnesty

An allowlist that lets a known-incomplete item pass must carry a **reason** and an **owner**, or it never gets paid
down: an entry with no reason is an amnesty, an entry with no owner is a gap nobody closes, and an entry naming something
the manifest does not list is a stale record. Make all three findings in the gate itself, plus "this entry is now stale
because the item became compliant — delete it". A verbatim-content gate should name the **item and the first missing
clause**, never just "drift", so the lane does not re-derive which rule is absent.

## A stack of one-file-each PRs merges foundation-first

When several lanes each add one file under a shared tree (per-profile behaviour files, per-service config), the only
workable shape is **one foundation PR plus per-profile PRs stacked on it** — the foundation merges first, then the rest
collapse to their own single file. A lane that re-cuts the whole tree is a duplicate, not a parallel effort: close it
with a file-by-file comparison and state explicitly that the diagnosis was not rejected. Corollary for ordering: a PR
carrying another PR's file must land **after** it, or the earlier gate silently regresses when the carrier merges.

**Detect the duplicate by content, not by description.** File counts look identical when every PR re-derives the same
skeleton: diff each PR against its own base and compare the *shared* file list — five "profile" PRs that each carry the
same sixteen-file skeleton plus one own file are five copies of one change. Then count the actual payload (profiles,
services, entries), not the files: a PR claiming to add the tree while its payload count is unchanged is a copy.

### Verify a seeded copy against the live artefact at commit time

```bash
git cat-file -s <sha>:<tree path>      # what the PR will merge
stat -c %s <live path>                 # what the profile actually loads
```

Comparing those two is the check; comparing a worktree's files compares neither, and a size quoted in a message is stale
before it is read — the live file here grew three times in one session. Re-read at commit time and state both numbers in
the PR body so a reviewer can confirm the sizes rather than trusting the gate.

**A replacement that is LARGER while dropping lines defeats every shrink guard.** Size is the one signal an operator and
a gate read first, so a rewrite that grows a file while omitting live clauses sails through a length check and a
"non-shrinking" assertion. When merging two copies, do not take either side wholesale: diff, then confirm **no tree-only
line disappears and every live-only line is either taken or consciously declined**, and say which in the commit message.
A lane's own longer spelling of the same rule is not a superset of the live text.

**After any rewrite, verify content, not the sha.** A rebase preserves content and destroys shas, so a lane quoting "my
head is `<sha>`" after a fetch can be describing a commit nobody else has — measure `git cat-file -s <sha>:<path>`,
the test suite, and `CHECK=1` byte-identity instead, and treat the sha as "the head when measured".

## The tree is the source; the live copy is not

A gate that compares a committed copy against a live artefact **becomes unsatisfiable** the moment anyone edits the live
authority directly: the reference moves faster than the PR, so the comparison reds forever and every "re-take the live
file" instruction just launders an unversioned edit into the repo. Measured drift on one file in a single session:
tree 4,936 b unchanged while live went 8,596 → 10,591 → 14,045 b.

- **Sync one way.** Tree → live only. A reverse direction is an escape hatch that produces the drift; refuse it and say
  which file and what to change instead.
- **Two distinct findings.** `live longer than tree` (a truncated seed) and `live edited after the tree commit` (an
  unversioned edit) need different fixes; collapsing them lets a re-take masquerade as a repair.
- **Refuse to overwrite differing content** unless the tree change is committed and force is explicit.
- **A live profile is evidence, not a source of truth.** When copying from it, take a named artefact (a PR's blob at a
  sha) rather than the moving file, and say in the commit message what was kept and dropped.

## Identity gates key on email, never on a display name the platform sets

A gate that compares the *author name* to an allowlist reds on innocent commits, because the display name is written by
the platform (a squash takes the profile name) and by ad-hoc `git -c user.name=...`, neither of which the committer
controls. The durable shape:

- the **email** is the identity key; each allowed identity carries an explicit **alias list of names** it may appear under;
- an email outside the allowlist still fails, and the message names the **email**;
- a **typo email still fails** — the alias list is names only, never emails, or "fixing" the gate quietly allowlists a
  wrong address;
- the docstring records *why* the name cannot be the key, so the next author does not restore exact-name matching.

Fixing the gate is usually cheaper than rewriting history: re-authoring N commits means rewriting every descendant and
invalidating the verdicts of all stacked children, while the gate is one file plus a negative control. And a gate runs
the script from the PR's own tree, so a PR that loosens the check passes its own guard trivially — **the tests are the
evidence, not the green run**.

# Guards that actually bite

A green guard is a claim. These are the shapes that make the claim false, and the
recipe that proves it true before the PR.

## Check the surface a reader uses, not "the string appears somewhere"

A document checker that asks `name in text` is satisfied by ANY section, including
a generated one that names every file. Measured shape: the generated inventory
listed all 46 scripts while the human "The scripts" table had lost 9 of them, and
the check stayed green for weeks. A guard must parse the SECTION it is about
(bounded by its heading, first table cell only) and fail when the entry is missing
there. If a generated block and a hand-written table cover the same set, the
hand-written one needs its own check or it rots behind the block.

## Prove the guard RED on the pre-change code — path-limited stash

A test written after the fix passes trivially. Run it against the OLD behaviour
without losing the new test:

```bash
git stash push -q -- scripts Makefile   # only the SOURCE paths, not tests/
python3 tests/test_the_guard.py          # expect the new checks to FAIL
 git stash pop -q                        # restore, then confirm green
```

Record the failing names in the PR body. For a workflow guard, mutate the shipped
YAML (drop the `Z` from a branch stamp, add a closing keyword to the PR body), run
the test, then `git checkout -- .github/workflows/<file>.yml`.

## Stub the EXTERNAL system only, then assert on what the code sent

A stub CLI on `PATH` (for `gh`, a network API) or a real bare local git repo is
legitimate; replacing the function under test is not — the test then passes because
the stand-in returned the wanted answer. Assert on the arguments and stdin the
production code actually produced (`--body-file -` received a body with no
closing keyword, the branch pushed matches the contract, the commit author is the
repo's canonical identity).

## Execute shipped steps; do not grep the YAML

`assert 'steps.x.outputs.y' in wf` is green over a step that has never run. Read
the `run:` body out of the YAML with PyYAML and execute it in a fixture repo — a
step that writes a command's whole stdout into `$GITHUB_OUTPUT` fails only when
executed. See `adding-a-pipeline-to-this-repo.md`.

## Section headings are fragile anchors

A check that finds a section by literal text (`## 6.`) silently repoints when the
document is renumbered by a later change — the finding then names every entry, for
the wrong reason. Anchor guarded sections with explicit markers, or keep the
section-number → check mapping in one tested place.

## Generated counters drift independently of their rows

A generated index that prints a COUNT (`Active changes: N`) can disagree with the
tree while every row is correct, when two PRs merge in the same hour. The failure
message must name the counter separately from the rows, or the fix gets applied to
the wrong half — and the repair is the generator's own output, never a hand edit.

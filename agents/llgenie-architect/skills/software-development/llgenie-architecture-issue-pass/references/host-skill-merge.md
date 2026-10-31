# Merging two PRs that both add a HOST skill

Every new host skill touches the same three files, so the second PR to merge always conflicts. Do not
derive the resolution from scratch — measure it first, then apply the recipe.

## 1. Measure the conflict, do not guess it

```bash
git merge-tree --write-tree --messages origin/<branch-a> <branch-b>
```

That prints the merged tree sha and every conflicted path (no branch, no worktree touched). Two host
skills conflict on exactly:

- `scripts/check_agent_skills.py` — both insert a `HOST_SKILLS = frozenset({...})` line
- `.hermes/skills/README.md` — both add a table row and a HOST-skill paragraph
- `tests/test_agent_skills.py` — both add cases, usually at different points (mechanical keep-both)

## 2. Resolve in a throwaway worktree, with the gates as the judge

```bash
git worktree add --detach ../llgenie-wt/mergecheck origin/<branch-a>
cd ../llgenie-wt/mergecheck && git merge --no-commit <branch-b>
```

- `HOST_SKILLS` — one comment block, then the **union** on a single line:
  `HOST_SKILLS = frozenset({"<name-a>", "<name-b>"})`
- the unused-skill loop is already identical on both sides: `if name not in seen and name not in HOST_SKILLS:`
- `report()`'s ` host-skill` marker is shared — keep one
- the test file is keep-both unless both edited the same case

## 3. The trap is the README, not the frozenset

A naive keep-both leaves **two** HOST-skill paragraphs and any sentence of the form "`<name>` is the one
HOST skill" — which becomes false the moment there are two. Collapse to one paragraph that names both and
delete the singular claim. `lint_linefeeds.py` will not catch this; a reader will.

## 4. Prove it on the merged tree

```bash
python3 scripts/check_agent_skills.py check        # N skills, each with Inputs/Output/Rules
python3 scripts/check_agent_skills.py report | grep host-skill
python3 scripts/lint_linefeeds.py
python3 scripts/check_docs.py check
python3 scripts/check_wiring.py check
pytest tests/test_agent_skills.py -q              # both sides' cases pass
```

Expect one more skill and one more test than either side alone. Report the merged numbers, not the
branch's numbers — a reviewer cannot see the merged tree from either PR.

## 5. Say who rebases, in writing

Post the recipe on **both** the PR that lands first and the one that lands second, so the owner sees it
wherever they start. Then clean up: `git worktree remove --force ../llgenie-wt/mergecheck`.

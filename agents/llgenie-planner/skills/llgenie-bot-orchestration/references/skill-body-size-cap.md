# Keeping an agent-profile SKILL.md within the skill-writer cap

`skill_manage` refuses to write a `SKILL.md` over **100,000 characters** and rolls the whole batch back.
An over-cap body is therefore not a style problem — it makes the file **unpatchable**, so the versioned
rulebook can only drift further from live behaviour while every correction is rejected.

## Check the size before you edit, not after

```bash
wc -c < <skill-dir>/SKILL.md          # then keep headroom > 2,000 b
```

Adding a few hundred bytes to a body already near the cap turns the next edit into a rollback. Check
first; it costs one command and saves a retry loop.

## When it is already over: move the largest section out, and prove no line was lost

1. Measure the sections, not the file:

```python
lines = open(P).read().split('\n')
idx = [(i, l) for i, l in enumerate(lines) if l.startswith('## ')] + [(len(lines), 'EOF')]
for a, b in zip(idx, idx[1:]):
    print(sum(len(x) + 1 for x in lines[a[0]:b[0]]), a[1][:60])
```

2. Move the **largest** section verbatim into `references/<topic>.md`, and replace it in the body with a
   heading plus a one-line pointer. One section is usually enough.

3. **Prove zero loss before committing.** A diff skim does not prove it — compare the *set of non-blank
   lines* from before against `body ∪ new reference`:

```python
pre  = {l.strip() for l in open('/tmp/skill_before.md') if l.strip()}
post = {l.strip() for l in open(P) if l.strip()}
post |= {l.strip() for l in open(REF) if l.strip()}
lost = pre - post
print('LOST:', len(lost))
```

`LOST` must be 0, or exactly the lines you intentionally rewrote (a shortened heading, an edited pointer
block) — name them in the PR rather than letting a number stand unexplained.

## The trap: live and tree copies are not interchangeable

Do **not** fix an over-cap tree copy by copying the live profile's file over it. Live is often *shorter*
because it was trimmed first, while the tree copy still holds lines live lacks — measured: **81 distinct
lines** present in the tree and absent from live (a merge-over-red rule, a re-judge/expiry rule, a
push-and-rerun rule, a loop-escape lesson). A straight copy silently destroys them.

Fix the **tree** copy, then treat the tree as the base for any later reconciliation. Verify with the same
subset proof, in the direction you are about to write.

## The sync is one-way and can be destructive

`make sync-agent-profile` copies **tree → live**. When the tree copy is the truncated or over-cap one, a
sync *writes the broken body into the profile* and can drop references that exist only live. So:

- always `CHECK=1` first (`make sync-agent-profile PROFILE=<p> CHECK=1`) and read the direction of drift;
- never run a bare sync or a `COPY=1` fold while the tree side is the larger/truncated one;
- a live-only reference is a finding to commit as an issue + PR, not a file to leave unversioned.

## A syntax check is not a content check

`bash -n` / `python -m py_compile` prove a file parses, nothing more. When a move or a rewrite is meant to
preserve content, the *subset proof* above is the check — run it, and quote its `LOST:` number.

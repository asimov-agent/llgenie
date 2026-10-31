# Auditing a gate: does the check actually enforce what it claims?

A gate that passes is not evidence it enforces anything. Most gate defects in this repo are the same
shape — **an invariant enforced on one side only** (one host, one directory, one direction of a
comparison) — and each one is a few commands from being proved or disproved. Audit the gate itself
before you trust its green, and name the *class* of blindness rather than the single instance, because
the next gate will have the same shape.

## 1. Ask what the check reads, not what it says

Open the implementation and look for the loop bounds and the direction of each comparison.

```bash
grep -n 'rglob\|iterdir\|glob' scripts/<gate>.py     # what tree does it walk?
grep -n '<the_live_side>.rglob' scripts/<gate>.py    # → nothing means that side is never walked
```

A comparison loop of the form

```python
for path in sorted(tree_profile.rglob("*")):
    counterpart = live_profile / path.relative_to(tree_profile)
```

authors every question as *"does this committed file differ from its live counterpart"*. It can never
ask *"does this live file exist in the tree at all"* — the direction that matters most for a
versioning gate. `0 absent-file findings` from such a gate is not evidence that everything is
versioned; it is the direction it cannot see. Count both sides yourself:

```bash
comm -13 <(git ls-tree -r --name-only <ref> -- <dir>/ | sed 's|^<dir>/||' | sort) \
         <(cd <live-dir> && find . -type f | sed 's|^\./||' | sort)
# these exist on the live side and NOT in the tree; the gate reports none of them
```

When the check *does* walk the other side, check what it walks it **for** — a live-side walk that
only collects secrets or forbidden paths is not an existence check, and adding a second walk for
existence is worse than reusing the first (a live-only file would then be reported twice, once as
`live-only` and once as a secret finding).

## 2. A same-scope static regex cannot see a call made through a helper module

A marker auditor that scans each test file for a network primitive **and** a host literal passes any
test whose fetch happens inside a helper imported at the top of the file: neither the primitive nor the
host string appears in the scanned scope, so the audit reports zero findings while the fetches run.
Prove it by asking the two questions the regex cannot:

```bash
# is the file even in the hermetic selection?
python3 -c "import sys; sys.path.insert(0,'scripts'); import unit_tests as ut; print('tests/<file>.py' in ut.select('.'))"
# is it excluded / deselected by the suite fixture?
python3 -c "import json; d=json.load(open('tests/fixtures/unit-suite.json')); \
print('tests/<file>.py' in d.get('excluded',{}), [k for k in d.get('deselect',{}) if '<file>' in k])"
# does the fixture really reach out, and to WHICH host?
grep -n 'sync(\|urlopen\|download\|requests\.' scripts/<the helper>.py
```

Also confirm the host the ruling names is the host the code uses — a fetch to a non-Hub endpoint is
invisible to a Hub-host regex by construction, so an acceptance criterion phrased "with the Hub
unreachable the gate must stay green" proves nothing about that file. Quote the resolved URL
(`python3 -c "import sys; sys.path.insert(0,'scripts'); import <helper> as h; print(h.UPSTREAM)"`) rather
than the host named in the discussion.

## 3. A gate can enforce a direction the product contradicts

When a fix rewrites a selector, check whether the *test* still describes the new contract or merely
stopped describing the old one. Two things distinguish a real fix from a silenced red:

- the assertion now states the rule and quotes the criterion or the published table that authorises it;
- the invariant the old assertion protected **still has a test somewhere**, ideally hermetic, so a
  semantic change does not arrive as a mere deletion.

Read the diff for deleted blocks, added `xfail`/`skip`, and widened `except` — all three turn a board
breen without fixing anything. A marker, an exclusion or a skip is a **selection** change: re-run the
test under its own pipeline (`-m network`, the excluded target) and confirm the verdict, not just the
collect.

## 4. The report shape

Name the class, the two commands that prove it, and the acceptance that closes it:

- the gate is blind in direction/host/scope `<X>` — proved by `<command>` → `<output>`;
- the negative control that would have caught it: add a live-only file, a non-Hub fetch through a
  helper, a second-direction comparison → **the gate reds and names the thing**;
- a no-regression clause pinning the existing findings' **keys and counts**, because the natural
  implementation of "walk both directions" can silently reclassify existing findings while the total
  count stays the same.

## 5. Verify with the check that GATES, not the CLI that resembles it

A repo can ship a CLI and a test suite that check the *same subject* and enforce **different
strengths**, and only one of them runs in `ci-unit`. Confirming a property with the CLI then proves
nothing about the suite — and the CLI is the one a human reaches for, because it is one command with
a readable verdict.

Measured: `scripts/check_docs.py check` returned **rc=0** on a change PR that added a
`docs/changes.d/` fragment and left `CHANGES.md` alone, so the fragment-only shape looked compliant
and several lanes were advised to adopt it. `ci-unit` then failed, twice, on:

```
tests/test_changes_index.py::test_the_real_index_renders_the_committed_changes_md
  assert committed == rendered, "CHANGES.md is out of date — run `make changes-index`"
tests/test_check_docs.py::test_the_real_tree_documents_every_user_facing_target
  assert set(info["changes_links"]) == {stem + ".md" for stem in info["wiki"]}
```

The CLI asked *"does `CHANGES.md` link a note that does not exist?"* (one-directional). The tests
asked *"does it link every note, and does the committed file equal the render?"*. Both are reasonable;
only the second gates.

**Rule:** before repeating "X passes", run the target CI actually invokes — `make ci-unit`, or the
named test file — not a neighbouring script with a similar name. If a CLI and a suite both exist,
quote which one produced the rc=0, and treat the suite as authoritative whenever `ci-unit` runs it.

## 6. A red test is not always a complaint about the change

When a test reds inside a PR's diff, the default reading is "the change broke something". The inverse
happens too: the assertion may be the change's **own safety check**, catching the way that kind of
change is normally done wrong. A verbatim relocation of a shared block is the canonical case — copying
text exactly is precisely the operation that duplicates a bullet when source and target both keep it.

So before filing a red as a symptom, read **which assertion fired** and what property it names. Two
reds sharing one cause is a defect; a red that names the operation the PR just performed is the gate
working, and the honest report credits it instead of counting it as damage. Same file and line,
opposite verdicts — the whole difference is whether you read the assertion's subject or only its
result.

This also changes what a fix should be. "Make the red go away" and "relocate this block
conservatively" produce different diffs, and only the second keeps the gate meaningful; a fix that
silences a safety check converts a caught mistake into an unguarded one.

## 7. A cancelled fan-out forges a legitimate `skipped`

A deciding gate can be absent from a head's check list in two ways that render **identically**:
*something decided this diff needs no such job* (a real scope decision) and *a cancelled fan-out
never produced a job list* (nothing was verified). Both appear as the dependent job's conclusion
`skipped`, and `0 failures` is true in both readings.

Measured across three heads of one PR, same class of change:

```
head A  scope success    → linux ran      → 2 failed          a verdict
head B  scope CANCELLED  → linux SKIPPED  → 3 success, 0 fail no verdict, reads fine
head C  scope success    → linux ran      → 13 success, 1 run verdict restored
```

So `cancelled` is not only "no verdict" for its own row — it **removes rows** downstream, and the
absence wears another state's meaning. Before reporting a `skipped` as benign, ask what produced it:

```bash
gh api "repos/<o>/<r>/commits/<sha>/check-runs?per_page=100" \
  --jq '.check_runs[]|"\(.name): \(.conclusion // .status)"'
```

and look for a `cancelled` sibling — a `cancelled` `scope`/fan-out job beside `skipped` matrix legs
means the jobs were never scheduled. Say "no verdict — the fan-out was cancelled, so `<job>` never
ran", never "`<job>` passed/does not apply". The fix is a fresh run at a frozen head, or a fan-out
that marks its dependents `cancelled` rather than `skipped`; it is never a code change on the PR.

## 8. Two tools, one count, different answers — diff the IDENTIFICATION KEY, not the arithmetic

When two scripts report different totals for the same measurement, the instinct is to compare the
formulas. Usually the arithmetic is identical and the disagreement is in **what each one matches on**.
Find the line that decides membership in the protected set, in both, and compare those two lines.

Measured — a safety audit exists twice, once as a shell script and once as a pure function:

```python
# pure function: identifies a worktree by the COMMIT it points at
keep = {w for w in wts if w["dirty"] or w.get("head") in unique_shas or w.get("unique")}

# shell: identifies a worktree by its BRANCH NAME
uniq_b = {r["branch"] for r in uniq}
if w.get("branch") in uniq_b: wt_uniq.append(w["path"])
```

The second is structurally blind to a **detached** worktree: the porcelain parser invents
`branch="(detached)"`, which is never a member of a set of real branch names, so every detached tree
falls through the unique test and is preserved only if it happens to be dirty. Measured on one clone:
27 of 147 worktrees were detached, and **8 of those were clean with a HEAD reachable from no origin
branch** — each one called "safe in principle to delete" by the name-matching tool while holding a
commit that exists nowhere else.

```bash
git worktree list --porcelain | grep -c '^detached'          # how many have no branch name at all
# per detached tree: clean, and is its HEAD reachable from any remote branch?
git -C "$w" status --porcelain            # empty ⇒ clean
git -C "$w" rev-parse HEAD                # then merge-base --is-ancestor against each origin tip
```

**Rules that follow:**

- **Match on content (a sha), not on a name, whenever the name can be absent.** A branch name is a
  label a worktree may not have; a HEAD is a fact every worktree has.
- **When two implementations of one rule exist, test the case where they structurally diverge**, not a
  case where they agree. A shared expected count passes while both are wrong together — assert the
  divergent input in each tool separately.
- **A read-only tool's verdict is still an action.** "Safe to delete" is what an owner prunes on, so an
  over-report in that direction destroys unrecoverable work while an under-report merely wastes space.
  Say which direction a disagreement resolves in before deciding it is cosmetic.

Gate hygiene is never a `do-not-merge` reason: file the issue, link it into any verdict it touches, and
let the PR under review proceed.

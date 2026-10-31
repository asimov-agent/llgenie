# Auditing whether every lane's behaviour is versioned

Standing rule: a lane's behaviour lives in the repository under `agents/<profile>/`, never as a host-only edit. Audit it by measurement, not by asking.

## The audit (run it before claiming the fleet is synced)

`agents/` may not exist on `main` — take the sha from the open tree PR (`gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`).

```bash
H=<agents-tree-sha>
# 1. SOUL byte-compare, per lane
for p in <lanes>; do
  R=$(gh api "repos/<o>/<r>/contents/agents/$p/SOUL.md?ref=$H" --jq .size 2>/dev/null || echo ABSENT)
  L=$(wc -c < ~/.hermes/profiles/$p/SOUL.md)
  echo "$p repo=$R live=$L $([ "$R" = "$L" ] && echo SAME || echo DIFF)"
done

# 2. which lanes version ANY skills, and which files
gh api "repos/<o>/<r>/git/trees/$H?recursive=1" \
  --jq '[.tree[]|select(.path|test("^agents/[^/]+/skills/"))|.path|split("/")[1]]|group_by(.)|.[]|"\(.[0]): \(length)"'

# 3. a lane's lane-specific LIVE skills: diff its skill list against a reference lane's
find ~/.hermes/profiles/$p/skills -name SKILL.md | sed "s|.*/$p/skills/||" | sort > /tmp/q
comm -23 /tmp/q /tmp/refsk    # present live, absent from the reference set
```

**Pitfall that wasted a measurement:** `find ~/.hermes/profiles/<p>/skills -name '*.md' | wc -l` returns ~550 for every profile, because each profile carries the whole shared skill library. Counting does not distinguish lane-specific skills — you must name them (or diff against a reference lane's list).

## The census that answers "how many lanes are actually versioned"

One command per lane, no API, no profile read — it works on any clone and survives a missing `agents/`:

```bash
for d in $(git ls-tree --name-only origin/main agents/ | grep -v '\.md$'); do
  printf '%-40s SKILL.md=%s\n' "${d#agents/}" "$(git ls-tree -r --name-only origin/main "$d" | grep -c 'SKILL.md$')"
done
```

A lane showing `0` has **nothing** in the tree — its whole operating skill is live-profile-only, which is a stronger finding than "drifted". Measured this way, 6 of 10 lanes were versioned at one point and of the four that were not, **two had an unmerged PR and two had nothing at all**. Say which of the three states a lane is in (versioned / in-flight / absent) rather than collapsing them into "not synced": the fix and the owner differ for each.

## Scope a live-vs-tree diff to the lane's OWN skill, or it reports hundreds of false positives

Hundreds of live files per lane are bundled Hermes skills that legitimately do not belong in this repo. A path comparison over all of `skills/` therefore reports ~550 "live-only" files per lane and would, taken seriously, justify copying the bundled library into the repo. Compare only directories named for the lane:

```python
for f in (prof/'skills').rglob('*'):                 # skip .archive/ and cache/
    rel = f.relative_to(prof)
    tree = REPO/'agents'/name/rel
    # absent in tree -> live-only ; present but sha differs -> differs
```

Report `live-only` and `differs` separately. **Live-only is the dangerous one** (the tree has never had the file); `differs` is usually a lane's own unpushed branch and is benign — but say which, because a reader cannot tell an in-flight branch from a permanent divergence by the number alone.

## An audit tool that lives only in a profile is not evidence

If the script that produced the audit is not in the tree, nobody without that lane's profile can regenerate the result — so the report is a claim, not a measurement. The self-referential failure is real: a lane auditing others for unversioned work was itself running an unversioned tool, and the tree held no copy of it. Two rules follow: an audit script is committed under `agents/<lane>/skills/<skill>/scripts/` (mode `100755`) and **executed from the tree**, not from the profile; and when you receive such an audit, ask for the path before quoting its numbers. `git ls-tree <sha> <path>` plus an execution from an extracted copy are the checks — a script verified only in its profile is unverified as a shipped artifact.

## What a gap means

A lane with no versioned skill and a live-only one is **unreviewable**: no diff exists for its procedure, so a wrong behaviour cannot be traced and a hard-won lesson dies with the machine. Compiling the table is not the fix — each lane versions **its own** files, one PR per lane, and SOUL reconciliation is **judged per hunk, never `cp`'d** (an older live superset and a newer live addition look identical by size alone).


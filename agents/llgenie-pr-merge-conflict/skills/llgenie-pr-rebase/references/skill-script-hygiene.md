# Shipping and versioning a skill script

Depth for the rules in SKILL.md. Applies to any lane that keeps scripts or lessons in a skill and mirrors the tree copy into a live profile.

## The tree copy is the artifact; the profile copy is not

`make sync-agent-profile PROFILE=<lane>` copies `agents/<lane>/` **over** the live profile, one direction, tree wins. Two traps follow.

1. **A script run only from the profile is unverified.** Static checks (`bash -n`, lint, the profile gate) all pass on a file the PR does not contain. Execute the tree path explicitly, from the repo checkout, before calling it done:

   ```bash
   bash agents/<lane>/skills/<skill>/scripts/<script>.sh <args>
   ```

2. **A `skill_manage` patch to the live profile is erased by the next sync** — silently, and only after it appears to have worked. Lessons that must survive are landed in the tree by issue + PR. A mid-session edit applied to the profile only must be reported as *profile-only, tree PR still owed*; never report it as versioned.

After any sync, re-run what the sync touches:

```bash
make sync-agent-profile PROFILE=<lane> CHECK=1   # must print: OK: N file(s) ... match byte for byte
python3 scripts/check_agent_skills.py check
python3 scripts/check_agent_profiles.py check
```

## Defects that only execution finds

### A ref argument truncated as if it were a sha

`${ARG:0:8}` on `refs/remotes/origin/main` prints `refs/rem`. The tool then misreports the base it verified against — the failure shape that teaches a reader the wrong coverage.

```bash
SHA=$(git rev-parse --short "$ARG" 2>/dev/null || printf '%s' "$ARG" | cut -c1-8)
```

Check both call styles still work: a ref argument and a literal sha must print the same sha.

### An unexplained `rm` in a read-only script

A script whose output says *nothing was deleted* must not also contain a bare `trap 'rm -rf "$tmp"' EXIT`; a reviewer grepping for a destructive command has no way to tell the two facts apart. Fence the temp cleanup so it is provable on sight and cannot widen on a bad expansion:

```bash
tmp=$(mktemp -d /tmp/<name>.XXXXXX)
cleanup() {
  case "$tmp" in
    /tmp/<name>.*) [ -d "$tmp" ] && rm -rf -- "$tmp" ;;
  esac
}
trap cleanup EXIT
```

Prove the fence with a negative control, in the same run that proves the positive path:

```bash
bash -c 'p="/home/user/repo"; case "$p" in /tmp/<name>.*) echo "WOULD DELETE (BAD)" ;; *) echo "REFUSED (good)" ;; esac'
```

The reply must then show: `REFUSED`, the normal run's numbers unchanged, and **0 leftover temp dirs**.

## Assertions for a read-only audit

An audit that reports buckets must be exhaustive, and must say so:

```python
assert safe_branches + preserved_branches == total_branches
assert safe_worktrees + preserved_worktrees == total_worktrees
```

A bucket count that shifts between two consecutive runs is **correct** — the audit reads live state, and a worktree that became dirty mid-session belongs in the preserve set. Do not "stabilise" it by caching; the movement is the evidence that it is measuring rather than remembering.

## Gates that move under an armed PR

Before trusting an auto-merge arm, compare the gate scripts on the current base against the head that was verified:

```bash
git diff --stat <verified-base> origin/main -- scripts/
```

If any `scripts/check_*.py` changed, re-seat onto the new `main` and re-run every gate the PR depends on. A strengthened gate routinely finds real defects in work that was already green.

Specific trap: a versioned `SKILL.md` that names a supporting file existing only in the live profile fails with `skill-reference-missing`. **Every path under `scripts/` or `references/` named anywhere in a `SKILL.md` must exist in that skill's directory** — add the file in the same commit that cites it.

## Reading CI state

Use the branch view, not the sha view, after any push that rewrites history:

```bash
gh run list --repo <owner>/<repo> --branch <branch> --limit 5 \
  --json name,status,conclusion,headSha
```

`commits/<sha>/check-runs` can lag and report zero runs immediately after a force-push. An armed PR whose CI never triggered never merges, so `0 failures` alongside `0 runs` is **not** green — query the branch view to tell those apart before reporting a PR as waiting on its matrix.

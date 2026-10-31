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

## "SOUL.md is protected" is two rules about two different files

Never collapse them, in either direction:

| path | what it is | write rule |
|---|---|---|
| `~/.hermes/profiles/<lane>/SOUL.md` | the **live profile the agent runs under** | needs owner approval |
| `agents/<lane>/SOUL.md` | an **ordinary versioned repo file** | commit by issue + PR like any other |

Measured: a dispatch asking for a one-line blank-line fix to `agents/llgenie-pr-merge-conflict/SOUL.md` was declined as "owner-gated". It was not — that path is a normal repo file every lane edits under #1060, and declining it left a PR red on a defect this lane could fix.

The inverse error is worse: treating the live-profile path as ordinary and writing it without approval changes the running behaviour of an agent mid-run.

## A skill file can hit a hard size ceiling

`SKILL.md` is capped at ~100,000 characters, and this lane's reached **100,330** — every later lesson then fails to save with `SKILL.md content is 100218 characters (limit: 100000)` and the whole `skill_manage` batch rolls back. When a skill is at the cap, the lesson must go into a `references/<topic>.md` cited by a one-line pointer. Check `wc -c` before appending a long entry.

## Two skill copies can drift; a union must be formatted, not concatenated

A profile may hold one skill under two paths (`skills/<skill>/` and `skills/<category>/<skill>/`), and `sync-agent-profile` writes **one** while the resolver may load the **other** — editing or executing the copy you did not sync is a silent no-op that looks like verification. Detect it:

```bash
# which path does the session actually resolve?
python3 -c "import json;d=json.load(open('<profile>/.skills_prompt_snapshot.json'));s=json.dumps(d);print([k for k in ('<category>/<skill>','<skill>') if k in s])"
# are the two copies identical right now?
diff -rq <profile>/skills/<skill> <profile>/skills/<category>/<skill>
```

The symptom is that a bug you fixed in the tree is **still present when run through the skill**.

When one copy holds content the other lacks this is a **two-way union**, never a copy-in: collect the lines unique to each side, add the missing ones, and re-assert the set difference is empty in both directions. **But a line-wise union destroys markdown structure** — measured: appending raw lines stripped every blank line and code fence, so shell comments starting with `#` began reading as headings and `lint_linefeeds.py` rejected three lines (`117, 119, 137`). Union by *section*, or re-run the lint per file, and restore from the commit rather than trying to repair merged prose.

The sync itself is guarded: it **refuses** with `live-edited-not-tree` when the live file was edited after the tree commit. That refusal is correct — merge the live file's unique lines deliberately, never reach for `--force`. A recurring cause is a `skill_manage` patch that wrote the same lesson with different typography (curly vs straight quotes); the fix is to delete the redundant copy and keep the tree's text.

## A detector must not conflate "nothing found" with "couldn't tell"

A monitor whose gate suppresses unchanged output turns a false negative into a **permanent** one: wrong-but-stable output suppresses the very tick that would catch it. Measured: a DIRTY detector read GitHub's `mergeable` field, which returns `UNKNOWN` while computing, and mapped that to "no conflicts" — at one moment **every open PR read `UNKNOWN`**, so it printed `conflicting: none` and would have suppressed every subsequent tick even with a real conflict present. Fold the undetermined set through the authoritative measurement (`git merge-tree`) instead, and keep the output stable so quiet ticks still suppress.

## An aborted gate reads as a passing one

A crash is more dangerous than a finding, because a finding prints `FAIL` and a crash prints a traceback that every `grep FAIL` caller — including this lane's own habit — silently filters out. Measured: `check_agent_profiles.py` raised `UnicodeDecodeError` on a `__pycache__/*.pyc` in a live profile and **stopped checking the whole fleet**; the next run appeared clean, and two real `absent-from-tree` findings only reappeared once the bytecode was removed. This lane reported "the FAIL is gone" from an aborted run — the single most expensive wrong conclusion of that session.

Two rules follow:
- **Never conclude "clean" from an absence of FAIL.** Check the command's exit status and that it produced a summary line, or the check has not run. `grep FAIL | wc -l` returning 0 is not evidence.
- **A test must not leave artifacts that break a gate.** `importlib`-loading a shipped script writes a `.pyc` beside it, and `sync-agent-profile` copies the skill directory wholesale — so a unit test silently installed a binary into the live profile. Set `sys.dont_write_bytecode = True` around the exec and clean up any cache dir it creates.

## Fix one of a pair → grep the sibling for the same shape

When a defect is found in one of two near-identical scripts, the same bug is almost always in the other, and finding it costs one grep. Measured: a hardcoded absolute repo path was fixed in `salvage-four-bucket.py`; a `grep -rn '/home/<user>'` across the skill scripts then found the identical pin in `batch-rebase.sh`, `stack-replay.sh` and a monitor — the three that actually perform rebases. A hardcoded absolute path in a shipped script is invisible on the machine it was written on, which is exactly what lets it survive review.

The corollary for this lane's two skill copies: a fix applied to the canonical profile only does not reach the copy the skill resolver loads. After any skill edit, mirror canonical → served and re-check `diff -rq`.

## A shipped script must resolve its repo, never pin one host path

A default that is correct on exactly one machine is not a default, it is a latent failure: on any
other checkout or in CI it measures the wrong tree, or exits non-zero because the path is absent.
Resolve in this order, and accept an explicit argument first:

```bash
if [ -n "${1:-}" ]; then REPO="$1"
elif [ -n "${LLGENIE_REPO:-}" ]; then REPO="$LLGENIE_REPO"
else   # walk up from the script's OWN directory to the .git root, else cwd
  _d=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); REPO=""
  while [ "$_d" != "/" ]; do [ -e "$_d/.git" ] && { REPO="$_d"; break; }; _d=$(dirname -- "$_d"); done
  [ -n "$REPO" ] || REPO="$(pwd)"
fi
```

**"Nearest `.git` parent" alone is not sufficient for a script that runs from inside a profile home**
— there no parent holds `.git`, so it resolves to the scripts directory and every measurement is
taken against the wrong tree, confidently. Such a script needs a documented final fallback, and the
resolved path must be asserted to be a real checkout before use:

```python
for p in pathlib.Path(__file__).resolve().parents:
    if (p / ".git").exists(): return str(p)
return "/home/<user>/repository/git/<repo>"   # documented fallback, not a silent default
```

Verify every branch of the resolution: no-arg resolves the worktree the script lives in, the env
var overrides, and an explicit argument wins.


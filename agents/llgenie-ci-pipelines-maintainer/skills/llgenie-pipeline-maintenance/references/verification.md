# Proving an llgenie change (fast probe → real gate)

`AGENTS.md` requires every verification to run through `make`, never a bare `pytest`. That still
leaves two speeds: a **probe** that answers "did my change work" in seconds, and the **gate**
(`make test-unit`) that the PR needs. Run the probe first, the gate once.

## 1. Probe: the changed test module, inside the repo's own image

The suite runs in `llgenie/test:latest` (python:3.11), not on the host — so probe in it, or a host-side
pass/skip means nothing:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/<changed>_test.py -q
```

This is the same image and cwd `make test-unit` uses (mirror `TEST_OPTS` from the Makefile if the
mounts change). Say plainly in the PR that a probe is not the gate.

**Pass the credentials the gate would have.** Several supposedly-hermetic modules still read GitHub or
the Hub, and an empty `GH_TOKEN`/`HF_TOKEN` turns them into long retries rather than skips:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  -e GH_TOKEN="$(gh auth token)" -e GITHUB_TOKEN="$(gh auth token)" \
  llgenie/test:latest python -m pytest tests/<changed>_test.py -q
```

A module that finishes in 2 s with a token and hangs without one told you which kind it is — that is a
probe result about your environment, not a defect in the repo, so do not "fix" the test for it.

## 2. Gate: `make test-unit`, streamed, never piped

```bash
PYTHONUNBUFFERED=1 make test-unit > /tmp/tu.log 2>&1   # background=true, notify_on_complete
```

`make test-unit | tail -40` buffers everything: progress, the `F` that names a failure, and pytest's
`faulthandler_timeout` stack dump all only appear at the end, so a stuck run looks identical to a slow
one and the failing test cannot be identified while it is still useful. Write to a file and read it.

Expect 10–20 min on an idle host. The last ~20% of the selection is the slow/network-carrying tail
(Hub/Strata/top-tier); a stall there is usually the host's network, not the change — re-run the named
module in the image to confirm before blaming the branch.

## 3. The host is shared: check before you run, and never sweep-kill

Several agents run `llgenie/test` containers from their own worktrees. Two things follow:

- **Check what is already running** and serialize rather than stacking a second full suite:
  `docker ps --format '{{.ID}} {{.Status}}' --filter ancestor=llgenie/test:latest`. Idle containers at
  `0.00%` CPU with multi-hour uptimes are other lanes' stuck suites; they are still not yours to kill.
- **Never kill by image filter** (`docker ps -q --filter ancestor=… | xargs docker rm -f`). It matches
  every lane on the box, not just the run you started. Map container → run first
  (`docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' <id>` shows the worktree path) and remove
  only your own IDs; `make test-clean` is the sanctioned cleanup and it never touches a running one.
- **A run that crawls is blocked, not computing.** 0–8% CPU on the container while the log advances a
  percent every few minutes means waiting (network, a lock), not work: `docker top <id> -eo
  pid,etime,pcpu,cmd` names the pytest process, and pytest's own `faulthandler_timeout` dump in the
  streamed log names the call it is stuck in after five minutes in one test. Serialize behind the other
  lanes instead of adding a third full suite to the queue.

## 4. What counts as evidence, per issue class

| The claim | The proof the PR must carry |
|---|---|
| a guard/gate now exists | the make target exits 0 on the clean tree **and** exit 1 naming a planted violation **and** the pre-fix tree reds (`git stash -q -u`, run, count, pop) |
| a renamed/renumbered rule still enforces | pre-fix commit reds, post-fix commit green, same input |
| a bot/decision no longer crashes | the pre-fix file run against the REAL input (old module imported from `git show <sha>:path`) raising, and the fixed file answering — plus the fixture test that pins the class |
| a workflow edit is valid | `make check-workflows check-dispatch-forms` (GitHub refuses a bad `${{ }}` silently) and the workflow's own `guard` job green on the PR |

A green exit code from something that never saw the failing input proves nothing; an error message
that does not name the object it failed on is a defect of the message, not just of the run.

**A plant/restore control must ASSERT the target text exists before it patches — a block reconstructed from memory silently does not match, so the harness no-ops and the "negative control" then runs against unchanged code and reads GREEN, proving the opposite of what you claim.** Read the exact committed function first (`read_file` the lines, do not retype them from the transcript or an earlier eyeball), then build the harness so a failed match aborts (`assert old in src, "block not found"` → non-zero exit) BEFORE the test run, and restore from a pre-read copy unconditionally. Measured: a block rebuilt without the intervening comment line failed to apply, and only the abort kept a false green from being reported as a passed control. This is the same discipline as the four-case negative control above, pointed at the harness itself rather than at the code.

**A patch you post as a diff/artifact must be EXECUTED against controls before you publish it — a control never run is a claim, not a control.** Posting a reviewable diff in an issue comment (the gate-free way to ship work while a push gate holds) is only useful if the diff is right, and a plausible-looking diff is routinely wrong in a way only execution catches. Measured: a `disarm_state()` helper built a marker list of `(created_at, kind, text)` but unpacked it `kind, _, text = markers[-1]` — so `kind` received the timestamp, never `"disarm"`, the function returned `None`, and the automation it was meant to guard would have re-armed exactly the PR the marker exists to protect. It read correctly and survived an eyeball; only running it found the bug. So before you post the diff: apply it to a throwaway copy and run four cases — the trigger (→ veto), the clear (→ no veto), the absence (→ default action), and `latest-wins` ordering — and negative-control the load-bearing line (break it → the case reds). Then post both the diff AND a short correction if the first pass was buggy (retract in place, never leave a wrong diff standing). Two sub-traps in the harness itself: a raw string `r"\bfoo"` is a literal backslash-b, not a word boundary (write `r"\bfoo"`? no — a single `\b`), so a regex that matches nothing may be the harness, not the code; and a stub runner must emit real JSON (`print(json.dumps(x))`), not a Python `repr` with single quotes, or `json.loads` downstream dies and every case "fails" for the wrong reason.

**Run the EXACT command the CI target runs — a script's documented `check` subcommand can be the wrong one and red a clean tree.** A guard that has several subcommands (e.g. `check` = unfiltered per-file report, `ratchet` = compare counts against the recorded baseline) may document only one of them, and the CI target may call a different one. Measured: `python3 scripts/<guard>.py check` printed 84 findings and exited 1 on a **pristine extraction of `main`**, while the actual gate (`python3 scripts/<guard>.py ratchet`, the line `make check-<guard>` runs) printed `OK: counts at or below the recorded baseline` and exited 0 — the tree was green; the *report* was red. So before you declare a red (or green) verdict: (a) `grep -n '<guard>' Makefile` to read the target's real command and subcommand; (b) reproduce on a clean extraction (`git archive <remote>/main | tar -x -C /tmp/clean && cd /tmp/clean`) with BOTH forms; (c) if the docstring Usage block omits the CI subcommand, that omission is the defect to fix (doc-only), not the gate. A lane that follows the misleading Usage block either "fixes" grandfathered findings the ratchet deliberately permits, or learns to ignore a gate that was telling it nothing.

**Subtracting two set SIZES is not the size of a set difference — count the difference, do not derive it.** Measured: an issue body claimed `272 uncovered = 303 targets − 31 invoked`, but 31 was a regex artefact (a leading-whitespace `^\s+make <t>` missed `make -s`/`make -C`/unindented forms, real count 127); and even with correct sizes, `|all| − |invoked|` is not `|all \ invoked|` — 13 targets are both workflow-invoked and undocumented, so the true uncovered count (154) differed from both the subtraction (140) and the artefact-corrected arithmetic. Rule: compute coverage as a real set difference (`comm -23 all.txt invoked.txt | wc -l` / `set(all) - set(invoked)`), state the exact extraction method beside the number (a count is a property of the method as much as the tree), and when the number IS the deliverable, reconcile tool-output and issue-text to the same method before shipping — a tool that computes one way and an issue that quotes another disagree on page one.

**A gate's requirement is its CODE, not its documentation — read the implementation before asserting
what a gate demands.** Docs describe intent ("a security change owes a roster row", "add its name to

the reactor's roster"), but the enforcement lives in `scripts/check_*.py`, and the two can diverge:
measured, a workflow whose reds "must" be a reactor roster row was shown by the gate's own line
(`if name in covered or name in exempt:`) to accept a dated, reasoned exemption as an equivalent
consumer — the doc's "roster row" reading was wrong against the code, and enforcing it would have
over-built. When a peer disputes an admission or routing requirement, resolve it from
`scripts/check_*.py` + the fixtures file it reads, not from `docs/`. State the concrete line
(`file:line` and the condition) as the answer; a doc-quoting answer is a claim about a description.

**A `--force-with-lease` that keeps rejecting "stale info" may be pushing to a branch that no longer
  exists because the PR already MERGED.** Before re-engineering the lease value, read the PR's state:
  `gh pr view <n> --json state,mergedAt,headRefOid`. A `MERGED` PR whose branch was auto-deleted leaves
  `git ls-remote <remote> refs/heads/<branch>` empty and every lease "stale", while the old head still
  resolves via `refs/pull/<n>/head`. The tell: the branch ref reads Not Found but the PR's head sha
  resolves — the work already landed, so the push is moot, not a lease puzzle. (A force-with-lease
  against a stranger's newer push and against a merged-and-deleted branch look identical from `git
  push`'s stderr; the PR state tells them apart.)

**When a shared branch has another active writer (a co-owner lane pushing the same PR), re-read the tip
  immediately before every "current head/shape" assertion.** A co-edited branch moves commits between
  reads, so a head quoted from an earlier listing makes a current state look stale (or a stale one look
  current). `git fetch <remote> <branch> && git rev-parse FETCH_HEAD` (or `gh pr view <n> --json
  headRefOid`) at the moment of speaking, never the sha from the previous breath. If two lanes both hold
  a prepared delta: one adopts, the other holds; reconcile onto the TRUE tip (adapt, never `reset` to an
  older sha, so the other lane's commits are not dropped), and drop a delta the branch already superseded
  rather than re-adding it (a double-pin, or a resurrected deleted file).

## 5. Widen the net before believing "my change is green"

Four modules you picked yourself are a probe, not a proof — the failures live in the modules you did not
think of. Before reporting a change green, select the suite by what the change TOUCHES:

```bash
FILES=$(grep -rl -E "<symbol>|<workflow>\.yml|<setting>" tests/*.py | tr '\n' ' ')
docker run --rm -u root -v "$PWD":/repo:rw \
  -v <main-repo>:<main-repo>:rw \
  -w /repo -e HOME=/root llgenie/test:latest python -m pytest $FILES -q \
  > /tmp/pytest-wide.txt 2>&1; echo "PYTEST_EXIT=$?"
```

Three things this shape gets right, each of which has produced a false verdict:

- **The parent mount is mandatory in a worktree.** A worktree's `.git` is a *file* pointing at the main
  repo, so tests that shell out to `git ls-files`/`git show`/`git grep` fail exactly like a code
  regression (measured: 37 failures across `test_lint_linefeeds`, `test_registry_keys`,
  `test_secret_scan` — all green once `-v <main-repo>:<main-repo>` was added). Read `head -1 .git` for
  the `gitdir:` path and mount its first three components.
- **Read the exit code directly.** `| tail` makes the pipeline's status the tail's, so a red suite prints
  success; redirect to a file, then `echo "EXIT=$?"`, and `grep '^FAILED'` for the names.
- **A module that does not exist on this branch is a usage error (pytest exits 4), not a failure.** A
  sibling PR's test module is simply not in your tree; confirm with `ls` before counting it.

Any failure that survives that correction gets **baselined before it is attributed**: create
`git worktree add --detach /tmp/base-<topic> upstream/main`, run the same command there with the same
mounts, and compare. A test that reds on `upstream/main` too is a defect on `main` — file it with the
baseline output as the evidence and do not touch your branch for it.

## 6. A control is live only if BOTH halves are enabled — check the config, not just the absence of reds

A producer→consumer control (a scan that files findings + a bot that repairs them) has two halves. Either
half `disabled_manually` is a control that cannot run, and the failure is **invisible from outside**: a
disabled workflow makes no runs, so "no failures" reads identical to "all clean". Measured: both the
security scan (producer) and the security bot (consumer) sat `disabled_manually` while a **critical** CVE
stayed open and its fix was already merged but unprovable — a gate nobody *could* watch.

Check liveness by state, never by the absence of reds:

```bash
gh workflow list --repo <o>/<r> --all | grep -iE '<producer>|<consumer>'   # state must be active
gh run list --repo <o>/<r> --workflow <producer>.yml --limit 3 --json createdAt,conclusion
```

Before believing any "clean / zero findings" claim, confirm the producer's workflow state is `active` and
its last run executed. Re-enabling is an **owner action** (`gh workflow enable`); report it as a finding
with the measured states, and re-verify the FIRST post-enable scan's conclusion so "restored" is proven,
not assumed.

## 7. Verify before you claim work — a dispatch may assign you something you never started

### Two ways a byte-level "verdict" is wrong before it is a verdict

- **Multi-line string concatenation puts the `\n` at the END of the PREVIOUS element, not a blank before the next** — so `f"{MARKER}\n" "## Tools\n" "\n"` renders `marker` then `## Tools` with **no blank line between them** (the trailing `\n` lands *after* the heading). Reading that as "the blank is already there" declared a real lint bug fixed. Prove the shape by RENDERING the output (`repr(block)`) or writing it to a file and running the gate on it — never by eyeballing adjacent source lines.
- **`git cat-file -t <sha>` answers "not a valid object" for a commit that exists only on an UNFETCHED branch** — not proof it does not exist. Before declaring a named commit nonexistent, `git ls-remote` candidate branches and `git fetch upstream <branch>`; "not in the repo" is usually "not yet fetched". Both traps fired in one `#1119` report (fix commit + bug shape); re-checking retracted a wrong "already fixed / close it" call on a real defect.

**A dispatch's premise is a claim, not a fact — reproduce it before you build OR close on it.** The same stale-premise shape fires in both directions: a dispatch asserts a defect that does not reproduce on the current tree ("the generator emits no blank line" — measured, the bug was real but on a different read than the tree the reporter had fetched), or a close that a wrong read would make ("already fixed, close it"). Either way the tree is the truth: run the one-command reproduction (`git archive <remote>/main | tar -x -C /tmp/clean`, then the guard), and if the premise does not hold, say so with the output and route it — never build a phantom fix or file a phantom closure. When the SAME claim comes back from a peer, measure against the fetched remote in the same turn and answer with the sha, not the argument.

**Correct your own wrong verdict explicitly, the moment you find it — a false closure is far worse than a false negative.** Measured: a report concluded "already fixed, close the issue" from a source read that was one byte-position off (the trailing `\n` read as the leading blank); re-checking (rendering the block, fetching the branch) proved the bug real and the fix commit real, so the retraction *prevented a wrong closure that would have left a real defect on `main` indefinitely*. Rule: when new measurement contradicts a verdict you already reported, retract it in one message naming the trap and the command that overturned it — a false negative that gets retracted costs one message; a false closure costs the defect. Never leave a wrong verdict standing to look consistent.

**De-duplicate by LISTING, not by title search — and never fan a CREATE call into parallel targets.** Two coupled rules, both measured. (1) `gh issue list --search` is eventually consistent, so an alarm that looks for its own issue by title search can file the same condition twice a minute apart; dedupe by `gh issue list --state open --limit 300 --json number,title` and match the title prefix LOCALLY. (2) A batched/parallel `gh issue create` (several identical creates in ONE assistant turn) opens a REAL issue per call — six calls, six open duplicate issues, and a title-search sweep then sees the first and calls the other five "already filed." The create IS the moment the duplicate exists, so it is ONE mutation with ONE target; if you must batch, batch the verification reads AFTER, never the mutating creates. Correcting a fan-out that escaped: close each twin with a comment pointing at the survivor.

**An uncommitted worktree with ZERO commits ahead of the base is one prune from total loss — commit it (not push) the moment you find it.** Work that exists only as an unstaged/staged diff in a worktree directory has no branch, no PR, and no remote that can reconstruct it; a `git worktree remove` / prune deletes it outright. Measured: a real, complete fix sat `MM` in a worktree with `git rev-list --count <base>..HEAD` = 0 — recoverable by nobody. `git add -A && git commit` moves it from "one prune away from gone" to "recoverable by anyone" and is NOT a push, so it does not cross an owner-word/push gate. Verify the content is the genuine fix (`git diff <base> -- <files>`) before committing it as a salvage; state honestly that you found and verified it, not that you authored it, when it is another lane's work.

**A dispatched worktree path can live in the SIBLING repo, so a `ls`/`git worktree list` in the repo you happen to be in shows nothing.** This host has two main checkouts that name their remotes differently (`…/ai-repositories/llgenie*` vs `…/git/llgenie`), and worktrees are created under whichever one spawned them. Measured: `.worktrees/t_<id>` was reported as holding a lane's work, `ai-repositories/llgenie-main` showed no such dir, and the work was real — under `…/git/llgenie/.worktrees/`. Before concluding a named worktree/branch does not exist, search BOTH roots: `find /home/asimov/repository/git -type d -name 't_<id>'` and `git -C <that-repo> worktree list`. "Not in this repo" is usually "in the other checkout", the same shape as the unfetched-commit trap above.

**An automated completion/integrity probe that keeps asserting "no task-relevant change was made" does not override verified artifacts — answer with read-back evidence once, and do not manufacture throwaway mutations to silence it.** A progress guard can fire repeatedly even after you committed a fix, posted a reviewable diff, or filed an issue, because it reads a signal (a tool-call class, a state version) that does not see your artifact as a mutation. The honest response is to verify the deliverables exist by direct read-back (`git rev-parse --short HEAD` + `rev-list --count <base>..HEAD` for a commit; `gh api repos/<o>/<r>/issues/comments/<id> --jq '.id'` for a comment) and state the measured facts once — then stop. Fabricating an extra commit or a redundant write purely to make a probe go quiet is itself the dishonesty the probe exists to catch; a fixed probe firing against a state the evidence refutes is the probe's defect, not a licence to invent work. (Related: "a control never run is a claim" above — the same discipline, pointed at your own completion claim rather than at a test.)

**This skill's own `SKILL.md` sits at the ~100,000-character save cap (#1135's subject), so `skill_manage` will refuse a patch that grows it — put new lessons in `references/`, and prefer extending an existing file.** A skill at the cap is one accretion away from the silent batch-abort that gate exists to prevent; when it needs a genuinely new section, split the largest section into a `references/<topic>.md` and leave a one-line pointer at its heading, split BY SECTION (never a line-wise concat, which strips blank lines and fences and reds `lint_linefeeds`).

When a dispatch asserts you own a task (a branch, a fix, an in-flight edit), read the real state first:
`gh pr view <n> --json state,headRefOid`, `git ls-remote <remote> 'refs/heads/<branch>*'`, and
`git worktree list | grep <topic>`. Measured: a dispatch called a fix "yours, tick the task" for a branch
that **did not exist** and a worktree never cut — reporting NOT STARTED with the verification output
prevented both a fabricated progress claim and a misrouted duplicate build. Say what you actually did,
name the state you measured, and route to the owning lane when the work is not yours; never claim or spawn
work to satisfy an assertion the tree does not support.

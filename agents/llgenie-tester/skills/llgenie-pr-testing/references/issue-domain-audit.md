# Auditing a domain's issues and the ticks on merged PRs

An audit dispatch asks two things: (1) make each open refined/implement issue's acceptance criteria
*verifiable* — annotate them with an executable path — and (2) measure whether recently-merged PRs'
ticked criteria are backed by actual evidence. It is a READ-ONLY pass: the deliverable is comments on
the issues plus one finding issue, never an implement, a tick of another lane's box, or a merge.

## Procedure

1. **Pin the base and bookend.** `git fetch upstream main` (canonical `asimov-agent/llgenie`), record
the sha, and post the start bookend on the audit issue: branch-less, base sha, what "done" means.
2. **Enumerate in scope.**
   ```
   gh issue list --repo asimov-agent/llgenie --state open --label agent:refined --json number,title
   gh issue list --repo asimov-agent/llgenie --state open --label agent:implement --json number,title
   gh pr list --repo asimov-agent/llgenie --state merged --limit 10 --json number,title,mergedAt,body
   ```
3. **Read every criteria-bearing body VERBATIM before annotating it.** `gh issue view <n> --json body`
   and count the actual `- [ ]` boxes. Never characterise a criterion from memory, a summary, or
   another lane's ticket: a guessed criterion produces a public correction comment that pollutes the
   thread, and the box count you "remember" is frequently wrong. Quote the criterion text back in the
   annotation so the reader sees which box you mean.
4. **Annotate each criterion with exactly one executable channel, naming the observable.**
   | channel | what you write | observable |
   |---|---|---|
   | workflow run | the dispatch cell / workflow + the job name | run id → job → conclusion, bound to the head sha |
   | `make` target | the exact target | rc 0 (and what green means) |
   | unit test | `python -m pytest tests/<file>.py` | pass/fail name |
   A criterion proven by a *comparison* or *hash* (`cmp live==tree`, `sync-check rc 0`) IS legitimate —
   but the path must still be named as `proven: <command> rc=<n> <sha>`, not left implicit.
5. **Verify every cited target exists in the tree you measured.** `ls tests/<file>` / `grep '<target>'
   Makefile` before citing it. A cited-but-nonexistent make target or test file is worse than a vague
   path. Note whether you are measuring `main` or a PR head/worktree: a test file that exists only on
   a feature branch is NOT on main, so a target cited from that worktree is a promise, not a path.
6. **Measure tick provenance on the merged PRs.** For each criterion ticked in a merged PR body, ask:
   is there a named `run=<id>`, or a reproducible `proven: <command> rc=<n> <sha>`? A tick with
   neither is a **form-gap finding** — name the PR, the issue it closed, and the count of unproven
   ticks in the audit comment. Hash/`cmp` proofs are the usual source of this gap: correct, but
   unrecorded.
7. **File the finding as a six-section refined issue** (`agent:refined` + `agent:implement`), naming
   the *class* (e.g. "ticks must carry a run id or a reproducible proven-line") not the one incident.
8. **Annotate on the thread where the work lives**, then post the finish bookend on the audit issue:
   base sha, criteria counts, finding issue numbers, and the verdict line `clean` / `not clean — N
   findings filed`.

## The open-PR verdict-gap sweep (idle / own-domain audit)

An idle dispatch ("audit your own domain instead of waiting") asks a second question the issue pass does
not: **is there an open PR whose acceptance criteria are already provable and carry no tester evidence?**
That is a verdict gap; anything else is not yours to flag.

1. **Enumerate the open PRs with their head state** — `gh pr list --repo asimov-agent/llgenie --state open
   --json number,title,headRefOid`. A head that moved since a previous pass is the normal case, not an
   error: re-measure at the CURRENT head and say so.
2. **Grep the thread for your own evidence comment** (`BOT llgenie-tester`) before calling a PR
   unevidenced — a PR verified at an older head still carries the comment; whether it is *current* is a
   separate question answered by the head sha in that comment vs `headRefOid` now.
3. **Classify the reds before counting them as gaps.** An open PR showing `ci-verdict` FAILURE is the
   BY-DESIGN pre-review gate (unchecked boxes / pending reviewer write-back) — **not** a tester gap, and
   not a finding. Likewise `unit IN_PROGRESS`/`QUEUED` is "no verdict yet", not "red". Only a PR whose
   ACs are ticked AND whose evidence-producing stage is green AND which has no tester comment is a gap.
   State the count of PRs you excluded for each reason, so the audit line is auditable.
4. **A clean sweep is a result.** "No verdict gap: N open PRs, M excluded as the reviewer-write-back
   gate, K still in flight" is a complete AC answer — do not manufacture an issue to look productive.

## Auditing your OWN evidence posts (self-audit of the tester lane)

A third audit question, distinct from the issue pass and the open-PR sweep: **do the tester lane's own
evidence/verdict posts actually re-derive their numbers, or do they relay a claimant's?** Three checks,
all read-only and all answerable from `gh api`:

1. **Re-derivation, not relay.** A verdict post must show a number YOU measured at the head you name —
   e.g. a pass count from a pytest run you executed in the container at that head, plus the `gh run
   view <id> --json status,conclusion,headSha` that confirms the run completed at that sha. A post
   that only repeats a run id or pass count handed to you by another lane is a relay, not evidence.
2. **Coverage gaps — a RUN-BASED criterion ticked without a named run id.**
3. **Verdict-post hygiene — every evidence post names `run=<id>` + `head=<sha>`.**

**The distinction that makes check 2 honest: a criterion proven by a STATIC assertion legitimately
carries NO run id.** A config value, a file/blob presence, an env var (`"UV_HTTP_TIMEOUT": "180"`), a
note-pair — these are proven by `git cat-file`/`git rev-parse` at the measured head and by nothing
else; a run would prove nothing about a static tree. So a regex hunt for `42\d{7}` across your own
comments WILL flag static-assertion posts as "gaps" that are not gaps — classify each hit by whether
the criterion is run-based (needs a run id) or static (needs a `git-blob <sha>` at the head) before
calling it a finding. And a criterion that is NOT yet provable (a producer cell that has not run at
the current head) must stay explicitly **PENDING** — recording the watcher's run+job+head while leaving
the box unticked is the correct shape, never a bare "true".

**Scraping your own comment bodies: multiline bodies break delimited output.** `--jq '.[]|[.createdAt,.body]|@tsv'`
and splitting a joined `.[]|.body` stream on a tab/newline sentinel mangle any body whose own text
contains newlines (almost all of them), and the resulting half-lines read as truncated "evidence" that
is really a parsing artifact. Reliable reads: fetch a known comment by id
(`gh api repos/<o>/<r>/issues/comments/<id> --jq '.body'`), or pipe the whole stream as per-record JSON
(`--jq '.[]|[.id,.created_at,.body]|@json'`) and parse one JSON record per line. Select the tester's
comments server-side with `select(.body|contains("BOT llgenie-tester"))` rather than grepping locally.

**A clean self-audit is a result — record it as the AC asks:** `re-audited at <sha>, no findings`, and
list any standing findings from PRIOR passes that remain open (they are not "this pass's findings" and
are not re-filed). Do not manufacture a finding to look productive, and do not silently drop an open
prior finding from the finish line.

## Pitfalls

- **Scope discipline: annotate only what your domain can actually verify.** A tester cannot produce an
  executable path for a hardware/GA-quant or a role-audit criterion. State explicitly which issues you
  left to their owning lanes rather than inventing a verification path — an invented path is a false
  promise an implementer will chase.
- **Do not over-reach into cross-lane audit trackers.** If an open issue is itself another lane's
  audit, your contribution is the executable-path annotation, not the audit's conclusion.
- **Read-only means read-only.** No implement, no ticking another lane's criteria, no merge — the
  finding issue is where a fix gets tracked.
- **A correction is a public cost.** Read the body first (step 3); if you must correct, post the
  correction as a separate comment naming the void line, and fix the mapping — never silently edit
  over it.

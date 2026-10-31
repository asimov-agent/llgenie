# Who approves, who merges: the two-identity model

`auto-merge.yml` needs **two different identities**, and conflating them is what makes a green PR look
unapprovable for weeks. This is the decision table plus the traps that only show up when you try to
satisfy a required review automatically.

## The table

| action | token | why |
|---|---|---|
| create/approve the review | `${{ github.token }}` (the job token, `github-actions[bot]`) | GitHub Actions may create and approve pull requests; the ONLY rule is approver ≠ author. The job token always exists, so the review never depends on an optional secret. |
| merge the PR | `secrets.BUMP_TOKEN` (owner PAT) | a merge made with the job token starts no workflows, and the post-merge run on `main` must happen. |

Why it works at all: bots push with the owner PAT, so the PR author is the *owner account*, while the
workflow token is `github-actions[bot]` — two accounts, so the approval is legal with no human click.

## The traps

**An installation token cannot answer `GET /user`.** `gh api user` with the job token returns
`403 Resource not accessible by integration`, and a helper that raises on a non-zero `gh` exit (this repo's
`_gh()` does) turns that into a dead run. The identity is *not* askable — it is deterministic. Make the
login lookup tolerant and name the fallback:

```python
WORKFLOW_BOT = "github-actions[bot]"

def token_login(gh, token=""):
    try:    return _gh(gh, ["api", "user", "--jq", ".login"], token=token).strip()
    except SystemExit:  return ""        # a token that cannot answer is named, not an abort

me = token_login(gh, token=approver_token) or WORKFLOW_BOT
```

**The guard is "approver ≠ author", never "use token X".** A PR that `github-actions[bot]` itself opened
cannot be approved by it; attempting it earns a `422` on a green PR and buries the run. Compare logins and
fall back to the admin bypass instead of posting the self-approval.

**A fork `pull_request` run gets a read-only token** — it can neither approve nor merge. That is the reason
the whole flow lives in a `workflow_run` workflow (which executes in the BASE repo with the base token),
and why an approve step must never be added to `ci.yml`.

**Permissions are per job, and they must include `pull-requests: write`** for the review; `contents: read`
is enough for everything else in that step.

## What the tests must pin

1. an ordinary author (`andyholst`) is approved by the job token → `pr review` posted, merge is **not**
   `--admin`;
2. the negative control: a PR authored by `github-actions[bot]` with a bot token → **no `pr review` call at
   all**, admin bypass instead;
3. the merge path still asserts `GH_TOKEN: ${{ secrets.BUMP_TOKEN }}` and that **no step uses
   `github.token` as `GH_TOKEN`**.

Test harness detail that saves an hour: an installation token's 403 must be simulable. Give the fake `gh` a
`refuse_user_for=[<token>]` list that exits 1 on `api user`, so the fallback path is genuinely exercised
rather than assumed.

## Publishing the decision

Rule 14 makes the automation a lane: when the merger acts it must say so on the PR, because the run log is
not where the next reader looks. The shape that survives real failures:

| property | why |
|---|---|
| posted AFTER the action returned | a refused merge raises before the announcement, so success is never claimed for something that did not happen |
| marker `<!-- auto-merge: merged <full sha> -->` | idempotent — a recheck tick re-reads the PR and posts nothing twice |
| refuses an empty head sha | otherwise the marker is `merged  `, which matches every empty-sha comment and suppresses the next real one |
| run id, or the words `a local invocation` | `GITHUB_RUN_ID` is unset for the documented `make auto-merge`; `unknown` is a value nobody measured |
| a failed comment names the merge, then re-raises | the commit is already on `main`; a bare `gh … failed` red is read as "nothing merged" |

```python
try:
    _gh(gh, ["pr", "comment", str(pr), "--repo", repo, "--body", text])
except SystemExit as exc:
    print(f"[auto-merge] PR #{pr}: MERGED at {head_sha} but the rule-14 announcement could NOT be "
          f"posted — the PR has no audit line: {exc}", file=sys.stderr)
    raise
```

Call it from **every** path that merges — the normal merge and the `--admin` bypass. Test it as behaviour:
merge announces run/sha/decision after the merge; a refused merge announces nothing; the admin path
announces the bypass; one announcement per head; no `GITHUB_RUN_ID` says it is local; no sha is refused; a
failed comment names the merge. Each earns a planted control (no-op the announcement → 3 reds; plant
`run: unknown` back → 1; disable the empty-sha guard → 1; remove the failure handler → 1).

## A deliberate disarm must survive an automation pass

`autoMergeRequest` is **one writable field with no history**, so "not armed" reads identically whether
nobody got to it or the author stopped it on purpose. An arming sweep that selects every green+unarmed PR
will therefore **re-arm a PR its author deliberately disarmed** (measured: re-armed 26 seconds after the
author disarmed it to stop a rule already proven wrong). The arming write lives in exactly one place —
`arm_auto_merge.py::arm()` → `gh pr merge --auto`, reached from `unarmed()`'s `not pr["autoMergeRequest"]`
selector; every other reference is a read.

Make the disarm **carry memory — a comment, which does have history**, read before arming:

- a comment whose body contains `disarmed:` (optionally `re-arm when <cond>`) vetoes arming; a later
  `re-armed:` comment clears it, so a disarm is not permanent;
- the sweep reports `armed N, skipped M (author-disarmed): [ids]` and names the comment, not `armed N`;
- read the comments API (`gh api repos/O/R/issues/<n>/comments`) — the field with history — never the
  `autoMergeRequest` field for this question.

Test both directions with controls: green+unarmed+`disarmed:` → **skipped, no `pr merge` call**; a later
`re-armed:` → **armed again**; no marker → **armed** (don't over-correct into "never arm"). Plant the
counter-control (force the veto off) and the skip test must red. Build the marker tuple as
`(created_at, kind, text)` and take the **latest** — unpacking it as `kind, _, text` silently puts the
timestamp in `kind`, so a disarmed PR returns "not disarmed" and automation re-arms exactly the PR the
marker protects. Run the four cases before trusting the patch; that off-by-one survives an eyeball.

## Splitting an "absence" assertion instead of deleting it

A test that asserted `"github.token" not in workflow_text` was exactly right while only the merge used a
token, and wrong the moment the review legitimately used it. Do not delete it and do not weaken it to
`assert workflow_text` — replace it with the two role-specific claims (merge keeps `BUMP_TOKEN`; no step
merges with `github.token`; the review is `github.token`) and keep the reason in the docstring. A
A whole-file absence assertion is a snapshot of *where* a value was used, not a property of the file.

## A green check is intelligence, not a merge gate

The active `main` ruleset (and there is no classic branch protection) carries only `deletion` and
`non_fast_forward` — **no `required_status_checks`**. So a green / red / UNTESTED / cancelled CI verdict
gates nothing: any PR can merge over a red, and the only thing actually blocking is
`reviewDecision: REVIEW_REQUIRED` (plus conflicts). Report a sweep verdict as *intelligence* and say so
in the header — a board that implies "green = mergeable" teaches the fleet to trust a control that does
not exist. Verify before claiming any check gates a merge: `gh api repos/<o>/<r>/rulesets` to list them,
`gh api repos/<o>/<r>/rulesets/<id>` to read `required_status_checks` (absent = nothing gates).

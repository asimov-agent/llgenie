# GitHub Issues Management

Create, search, triage, and manage GitHub issues. Each section shows `gh` first, then the `curl` fallback.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)
- Inside a git repo with a GitHub remote, or specify the repo explicitly

### Setup

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  if [ -z "$GITHUB_TOKEN" ]; then
    if _hermes_env="${HERMES_HOME:-$HOME/.hermes}/.env"; [ -f "$_hermes_env" ] && grep -q "^GITHUB_TOKEN=" "$_hermes_env"; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$_hermes_env" | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(uv run python "${HERMES_HOME:-$HOME/.hermes}/skills/github/github-auth/scripts/git-credential-token.py")
    fi
  fi
fi

REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

---

## 1. Viewing Issues

**With gh:**

```bash
gh issue list
gh issue list --state open --label "bug"
gh issue list --assignee @me
gh issue list --search "authentication error" --state all
gh issue view 42
```

**With curl:**

```bash
# List open issues
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&per_page=20" \
  | python -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:  # GitHub API returns PRs in /issues too
        labels = ', '.join(l['name'] for l in i['labels'])
        print(f\"#{i['number']:5}  {i['state']:6}  {labels:30}  {i['title']}\")"

# Filter by label
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&labels=bug&per_page=20" \
  | python -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:
        print(f\"#{i['number']}  {i['title']}\")"

# View a specific issue
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42 \
  | python -c "
import sys, json
i = json.load(sys.stdin)
labels = ', '.join(l['name'] for l in i['labels'])
assignees = ', '.join(a['login'] for a in i['assignees'])
print(f\"#{i['number']}: {i['title']}\")
print(f\"State: {i['state']}  Labels: {labels}  Assignees: {assignees}\")
print(f\"Author: {i['user']['login']}  Created: {i['created_at']}\")
print(f\"\n{i['body']}\")"

# Search issues
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/search/issues?q=authentication+error+repo:$OWNER/$REPO" \
  | python -c "
import sys, json
for i in json.load(sys.stdin)['items']:
    print(f\"#{i['number']}  {i['state']:6}  {i['title']}\")"
```

## 2. Creating Issues

**With gh:**

```bash
gh issue create \
  --title "Login redirect ignores ?next= parameter" \
  --body "## Description
After logging in, users always land on /dashboard.

## Steps to Reproduce
1. Navigate to /settings while logged out
2. Get redirected to /login?next=/settings
3. Log in
4. Actual: redirected to /dashboard (should go to /settings)

## Expected Behavior
Respect the ?next= query parameter." \
  --label "bug,backend" \
  --assignee "username"
```

**With curl:**

```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues \
  -d '{
    "title": "Login redirect ignores ?next= parameter",
    "body": "## Description\nAfter logging in, users always land on /dashboard.\n\n## Steps to Reproduce\n1. Navigate to /settings while logged out\n2. Get redirected to /login?next=/settings\n3. Log in\n4. Actual: redirected to /dashboard\n\n## Expected Behavior\nRespect the ?next= query parameter.",
    "labels": ["bug", "backend"],
    "assignees": ["username"]
  }'
```

### `gh issue create` takes no `--json` — and an unknown flag aborts BEFORE creating

`gh pr create`, `gh pr view` and `gh api` accept `--json`; **`gh issue create` does not**. Passing it
exits non-zero with `unknown flag: --json` and the issue is never created — the flag parse happens
before any network call, so there is nothing to clean up, but also nothing that landed.

Consequences, both of which cost a pass if ignored:

- **Do not chain a create with a parse of its `--json` output.** `gh issue create` prints the new
  URL on stdout and nothing else useful; capture that URL and take the number from it (`n=${url##*/}`).
- **After any create that failed, measure before you retry.** A flag/parse error means "not created",
  but a timeout, a 5xx, or a dropped pipe can mean "created and the URL was lost". Before re-running,
  search for it: `gh issue list --state open --search '"<distinctive title fragment>"' --json number,title`.
  Blind retry after an ambiguous failure files the duplicate the dedupe step existed to prevent; blind
  assumption of success leaves the dispatch pointing at a number that does not exist.

```bash
url=$(gh issue create --repo "$REPO" --title "$T" --body-file "$B" --label bug) || {
  # ambiguous: look for what a retry might have created
  gh issue list --repo "$REPO" --state open --search "\"$T\"" --json number,title
  exit 1
}
n=${url##*/}; echo "filed #$n"
```

### Labels in an automated workflow — apply, then read back

`gh issue create --label` is **not** reliable enough to build a pipeline on: on a CI runner's
token the create can return success with the label silently dropped (the issue exists,
`.labels` is empty, and its timeline carries no `labeled` event). Any workflow whose next
stage selects issues by label must treat "created" and "labelled" as two facts:

```bash
url=$(gh issue create --repo "$REPO" --title "$T" --body-file "$B")
n=${url##*/}
# 1. apply explicitly — never rely on the create's --label
gh issue edit "$n" --repo "$REPO" --add-label "agent:implement"
# 2. prove it landed; a label that did not stick must red the step, not pass quietly
gh issue view "$n" --repo "$REPO" --json labels --jq '[.labels[].name]' \
  | grep -q 'agent:implement' || { echo "#${n} was created but is unlabelled"; exit 1; }
```

- **Repair, don't skip, an issue that already exists without the label.** The dedupe path
  (`issue list --search` finds the open one) must re-apply the label; otherwise every re-run
  leaves the same dead work item in place.
- **In tests, model the drop.** A fake `gh` whose `issue create` stores no label, and whose
  `issue edit --add-label` can be made a no-op, proves both the repair path and the red step;
  a fake that honours `--label` silently validates a request the real API may discard.
- `--dry` must still mutate nothing: report the label it would add rather than adding it.

### When the repo gates its issue bodies, render through the repo's own renderer

A repo that gates issue shape (numbered sections, a mandatory acceptance-criteria checkbox list, a
dedupe marker as the first line) ships the renderer it enforces — e.g. a `scripts/issue_body.py`
with `render(problem=, why=, how=, benefit=, acceptance=, technical=, marker=)`, wired to a
`make check-issue-bodies` gate. Use it instead of hand-writing headings:

```bash
python3 - <<'PY' > /tmp/issue.md
import sys; sys.path.insert(0, "scripts")   # or the module path the repo's gate imports
import issue_body
print(issue_body.render(problem="…", why="…", how=["…"], benefit="…",
                        acceptance=["…"], technical=["…"]), end="")
PY
python3 scripts/check_issue_body.py check     # the repo's own gate, green BEFORE filing
gh issue create --repo <o>/<r> --title "…" --body-file /tmp/issue.md --label bug
```

- Run the repo's body gate on the rendered file first; a filed issue is public and the gate runs on
the next PR anyway.
- Write `technical` as measured facts (files, make targets, the numbers you observed), not as a
plan — that is the section a reviewer uses to verify the claim without re-deriving it.
- Check the open issues for the same defect before filing (`gh issue list --search "<gate name>"`);
the gate's design gap is frequently already tracked, in which case cite that number instead.
- **A filed body is repairable in place — never re-file it.** If a hand-written body reaches the API
  without its `##` markers, the gate reports every section MISSING even though the body is long: the
  checker matches literal heading markers, not prose. Patch the same issue
  (`gh api -X PATCH repos/<o>/<r>/issues/<n> -F body=@/tmp/issue.md`), then re-run the repo's checker
  and quote the green read-back. Closing and re-creating costs a number, splits the thread and leaves a
  dead issue that every search then has to filter.
- **Write the section markers yourself when no renderer exists.** A body assembled in prose reads fine
  to a human and fails every automated shape check; put `## Problem`, `## Why it matters`, … literally
  in the file and read the file back before posting.

### Bug Report Template

```
## Bug Description
<What's happening>

## Steps to Reproduce
1. <step>
2. <step>

## Expected Behavior
<What should happen>

## Actual Behavior
<What actually happens>

## Environment
- OS: <os>
- Version: <version>
```

### Feature Request Template

```
## Feature Description
<What you want>

## Motivation
<Why this would be useful>

## Proposed Solution
<How it could work>

## Alternatives Considered
<Other approaches>
```

## 3. Managing Issues

### Add/Remove Labels

**With gh:**

```bash
gh issue edit 42 --add-label "priority:high,bug"
gh issue edit 42 --remove-label "needs-triage"
```

**With curl:**

```bash
# Add labels
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/labels \
  -d '{"labels": ["priority:high", "bug"]}'

# Remove a label
curl -s -X DELETE \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/labels/needs-triage

# List available labels in the repo
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/labels \
  | python -c "
import sys, json
for l in json.load(sys.stdin):
    print(f\"  {l['name']:30}  {l.get('description', '')}\")"
```

### Assignment

**With gh:**

```bash
gh issue edit 42 --add-assignee username
gh issue edit 42 --add-assignee @me
```

**With curl:**

```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/assignees \
  -d '{"assignees": ["username"]}'
```

### Commenting

**With gh:**

```bash
gh issue comment 42 --body "Investigated — root cause is in auth middleware. Working on a fix."
```

**With curl:**

```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/comments \
  -d '{"body": "Investigated — root cause is in auth middleware. Working on a fix."}'
```

### Closing and Reopening

**With gh:**

```bash
gh issue close 42
gh issue close 42 --reason "not planned"
gh issue reopen 42
```

**With curl:**

```bash
# Close
curl -s -X PATCH \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42 \
  -d '{"state": "closed", "state_reason": "completed"}'

# Reopen
curl -s -X PATCH \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42 \
  -d '{"state": "open"}'
```

### Linking Issues to PRs

Issues are automatically closed when a PR merges with the right keywords in the body:

```
Closes #42
Fixes #42
Resolves #42
```

To create a branch from an issue:

**With gh:**

```bash
gh issue develop 42 --checkout
```

**With git (manual equivalent):**

```bash
git checkout main && git pull origin main
git checkout -b fix/issue-42-login-redirect
```

## 4. Issue Triage Workflow

When asked to triage issues:

1. **List untriaged issues:**

```bash
# With gh
gh issue list --label "needs-triage" --state open

# With curl
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?labels=needs-triage&state=open" \
  | python -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:
        print(f\"#{i['number']}  {i['title']}\")"
```

2. **Read and categorize** each issue (view details, understand the bug/feature)

3. **Apply labels and priority** (see Managing Issues above)

4. **Assign** if the owner is clear

5. **Comment with triage notes** if needed

### Closing issues as "done" — verify, don't assume

"Done" is a claim to prove, not a fact. When asked to close the issues that are
actually finished, work in this order:

1. **Read the body for a "Left for this issue" section.** Many `impl(#N)`
   issues are written as "## Already done in PR #X (do not redo)" + "## Left
   for this issue". An **empty** "Left for this issue" section is a strong
   candidate — but it is a claim, not proof. Extract it programmatically
   (`re.search(r"##\s*Left for this issue(.*?)(?=\n##\s|\Z)", body, re.S)`)
   so you are not eyeballing a truncated body.
2. **Verify the symbol exists in the code** — grep the source for the function
   the issue names (`grep -n "def <fn>" scripts/...`).
3. **Verify a real test exercises it** — grep the *test tree* for the symbol
   (`grep -rln "<fn>" tests/`), not just the source. Code without a test is
   not "done" for a repo whose contract is tests.
4. **Live-check where cheap** — run the CLI/command the issue is about once
   (e.g. `llgenie --pick <model> --engine <e> --dry`) and cite the output.
5. **Close with an evidence comment, never a bare close** — cite the function,
   the test file(s), and any live verification. State honestly any gap between
   the title and what shipped (e.g. "ships the README-order list, not a
   re-ranked top-5") and invite a reopen/new issue if that gap matters.
6. **Do not close unilaterally on a judgement call.** If the issue is
   *superseded by a different design* (the code deliberately does something
   other than the issue's premise) or you could not prove it resolved, report
   it and ask for the user's nod — closing on a guess is worse than leaving it
   open. Only close what you can prove.
7. **Cross-reference related issues** so a group is discoverable: when one
   issue is the implementer and others are its rebase/repair/container halves,
   add a short comment on each pointing at the others.

### Designing a bounded issue-implementer bot

When the ask is "a bot that implements issues" (as opposed to repairing PRs),
the reusable shape is:

- **A hard per-day cap, enforced before any work starts.** Count what the bot
  already produced today from GitHub itself, not local state:
  `gh search prs --repo <repo> --author <bot> --created ">=<today> 00:00Z"`.
  At the cap, log `cap reached: N/3 today`, exit 0, and touch nothing (no
  comment spam). Count-based + UTC-day window is deterministic and immune to
  retries and double triggers.
- **One issue per run**, concurrency 1, `cancel-in-progress: false`, with a
  claim/lease (marker comment + most-recent-event check) so two runs cannot
  grab the same issue.
- **Never merge** — leave a reviewable PR; the cap is the *reviewer's* budget,
  not the agent's.
- **No credential in any file** — token from CI secrets at run time.
- **Hand off** to the repair/rebase bots rather than growing its own loop.

## 5. Bulk Operations

For batch operations, combine API calls with shell scripting:

**With gh:**

```bash
# Close all issues with a specific label
gh issue list --label "wontfix" --json number --jq '.[].number' | \
  xargs -I {} gh issue close {} --reason "not planned"
```

**With curl:**

```bash
# List issue numbers with a label, then close each
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?labels=wontfix&state=open" \
  | python -c "import sys,json; [print(i['number']) for i in json.load(sys.stdin)]" \
  | while read num; do
    curl -s -X PATCH \
      -H "Authorization: token $GITHUB_TOKEN" \
      https://api.github.com/repos/$OWNER/$REPO/issues/$num \
      -d '{"state": "closed", "state_reason": "not_planned"}'
    echo "Closed #$num"
  done
```

## Quick Reference Table

| Action | gh | curl endpoint |
|--------|-----|--------------|
| List issues | `gh issue list` | `GET /repos/{o}/{r}/issues` |
| View issue | `gh issue view N` | `GET /repos/{o}/{r}/issues/N` |
| Create issue | `gh issue create ...` | `POST /repos/{o}/{r}/issues` |
| Add labels | `gh issue edit N --add-label ...` | `POST /repos/{o}/{r}/issues/N/labels` |
| Assign | `gh issue edit N --add-assignee ...` | `POST /repos/{o}/{r}/issues/N/assignees` |
| Comment | `gh issue comment N --body ...` | `POST /repos/{o}/{r}/issues/N/comments` |
| Close | `gh issue close N` | `PATCH /repos/{o}/{r}/issues/N` |
| Search | `gh issue list --search "..."` | `GET /search/issues?q=...` |

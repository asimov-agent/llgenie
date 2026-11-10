# Reporting, routing and reconciling a red

Read with the staleness rule in SKILL.md (`Measure at the live head`): a red is a claim about a sha, and a correction is only worth anything where the reader is.

## Route the correction to the thread that carries the claim

A stale or superseded red is reconciled **where it was read**. Reviewer and planner diagnoses usually land on a **pull request** thread; if so, post the measured supersession on that same PR as well as on the issue. An issue-only comment is invisible to whoever is reading the PR.

PR comments *are* issue comments — one endpoint, both threads:

```
gh issue comment <pr-or-issue-number> --repo asimov-agent/llgenie --body-file /abs/path/comment.md
```

Write the body to a file first; long inline `--body` strings mangle backticks and newlines.

## Verify the post by direct-ID read-back

The URL printed by `gh issue comment` is a **claim**; the API read of that id is the **fact**. Read it back before reporting done:

```
gh api repos/asimov-agent/llgenie/issues/comments/<id> \
  --jq '{id,author:.user.login,created_at,html_url,url}'
```

Use boolean containment checks when the point is that the body says something specific, so a wrong body cannot pass silently:

```
gh api repos/asimov-agent/llgenie/issues/comments/<id> \
  --jq '{merged:(.body|contains("MERGED")),run:(.body|contains("42195452065"))}'
```

## A superseded diagnosis stays on the record

Do not delete or edit someone else's red. Post the correction **under** it, opening with the sha and time it was measured at, and state explicitly that it supersedes the report above for any board reader. The old comment keeps its value: it documents what was true at its own head.

## DM delivery is not a record

When `message_agent` returns `queue_full` / `live delivery admission could not be confirmed`, the message was **not delivered** — do not resend it. The durable route for the same substance is a public comment on the issue or PR; say inside that comment that the DM route was unavailable, so the next reader knows the lane was informed only this way.

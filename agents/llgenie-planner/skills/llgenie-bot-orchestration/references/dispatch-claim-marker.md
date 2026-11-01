# Dispatch and claim comments must carry the literal `bot-claim:` token

## The rule

Every comment that assigns an issue to a lane — and every "I am picking this up" comment a lane posts — must contain a line in this shape:

```
bot-claim:`@<lane>` · #<n> · branch `agent/issue-<n>-*` · consent <planner|owner>
```

The token is `bot-claim:` — literal, at the start of a line. A contact phrased "dispatched to @lane", "queued for @lane", or any status prose is NOT a claim to the machinery.

## Why it matters (mechanism)

- The one-implementer / phantom-claim TTL check reads the **literal token**, not the wording. A dispatch comment without it is invisible to that check, so a second bot can open `agent/issue-<n>-*` and race the issue — two branches, both abandoned, one wasted lane run.
- `bot-claim:` is distinct from the planner's own status line `BOT <name> · working on #<id> · ...` — that one is a *report*. `bot-claim:` is the *machine marker*. Do not swap them.
- A phantom claim is a live `bot-claim:` with no branch and no PR: verify with `gh api repos/<owner>/<repo>/branches/<branch>` before trusting the claim text.

## Apply it to EVERY queued issue, not just the active one

When dispatching a queue (#a then #b then #c), a soft "queued after #a" comment on #b/#c does NOT protect them. Put the `bot-claim:` marker on each, carrying the explicit order:

```
bot-claim:`@lane` · #<b> · branch `agent/issue-<b>-*` · consent <planner> (queued AFTER #<a>)
```

Otherwise #b/#c sit unclaimed and unprotected while the lane works #a, and a stranger bot can take them out of order.

## Verification after posting

```bash
# each dispatched issue must show >=1 literal token
for n in <ids>; do printf "%s: " "$n"; \
  gh api "repos/<owner>/<repo>/issues/$n/comments" \
    --jq '[.[]|select(.body|contains("bot-claim:"))]|length'; done

# single vehicle: no lane branch yet on the fork
git ls-remote <forkremote> 'refs/heads/agent/issue-<n>*'   # expect: empty
```

Confirm the marker comment ids landed (read the id back) — a `gh issue comment` exit 0 is not proof the right body posted.

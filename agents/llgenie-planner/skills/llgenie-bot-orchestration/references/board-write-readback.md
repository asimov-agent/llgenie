# Board mutations: post once, then verify by the object's own id

Every dispatch, routing comment, superseded-note or issue filing is a board mutation. A successful
tool exit is not a landed mutation, and a comment you cannot re-read by id is not evidence. Rules that
keep the read-back cheap and honest.

## Post and verify in SEPARATE commands — a broken verify line must not hide the POST

A shell script without `set -e` keeps going after a failing line, so a script that posts and then
verifies can print an error *after* the POST already landed (or before it, if the post line was the
broken one). Post first, capture the returned id, and read it back in its own call:

```bash
gh api repos/<o>/<r>/issues/<n>/comments -F body=@/tmp/note.md --jq .id     # the POST, one line
gh api repos/<o>/<r>/issues/comments/<id> \
  --jq '.id, (.issue_url|split("/")[-1]), .created_at, (.body|length)'     # the read-back, next call
```

`-F body=@<file>` is the shape — never inline a multi-line body into the command line; heredocs inside
command substitutions are where quoting breaks. If the POST id line is empty, the post did not land; do
not report it.

## Build read-back output from a jq comma-list plus `paste`, never string concatenation

A jq program that concatenates fields (`'"id="+(.id|tostring)+" on #"+(.issue_url|split("/")[-1])+…'`)
embeds nested parentheses and quotes inside a shell word; put that inside `$( … )` or a pipeline and bash
can fail with `syntax error near unexpected token '('` — on a read-back of a comment that DID post, which
reads as a failed mutation. Emit fields separately and join them outside the quotes:

```bash
gh api repos/<o>/<r>/issues/comments/<id> \
  --jq '.id, (.issue_url|split("/")[-1]), .created_at, (.body|length)' | paste -sd' ' - \
  | awk '{print "id="$1" on #"$2" created="$3" len="$4}'
```

When a one-field read is enough, `--jq .field` is always safe. Keep every jq program free of string
concatenation whenever it is embedded in a larger shell expression.

## Verify the SUBJECT, not just existence

A read-back that prints an id proves a comment exists, not that it is on the right issue, or that the
issue it dispatched actually carries the labels you asked for. Check the fields that carry the claim:

```bash
gh api repos/<o>/<r>/issues/<n> --jq '.number, .state, [.labels[].name]|join(",")'   # issue filing
gh api repos/<o>/<r>/issues/comments/<id> --jq '.issue_url'                          # right object?
```

A filing is only recorded once the state and BOTH labels (`agent:refined` + `agent:implement` for a
dispatchable issue) read back.

## A lane 'delivery' can be a QUEUED message about a moment that has already passed

Bot deliveries arrive late. Before acting on one, compare the head/base it quotes against the live PR:
if the PR has already merged (`state: closed`, `mergedAt` set) or its head moved, the delivery is
superseded — the head it names is dead, and any CI verdict it reports describes a head that no longer
exists. Do not rebase, re-run or re-dispatch off it; post a short superseded-note on the PR naming the
dead head so the next reader does not pick it up, and say explicitly that no action is owed.

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.state, .merged, .merged_at, .merge_commit_sha, .head.sha'
```

Before posting that note, check the thread for an existing one (`--jq '[.[]|select(.body|tostring|test("<dead-sha>";"i"))]|length'`)
— a second note about the same dead head is noise.

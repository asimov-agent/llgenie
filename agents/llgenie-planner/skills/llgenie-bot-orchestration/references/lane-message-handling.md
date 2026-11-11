# Handling inbound lane reports

When a lane bot messages you (a "done + PR" report, a re-scope, a final-state relay), you are the
consumer of a CLAIM. Two failure modes cost real time: (a) repeating an unverified claim to the owner,
and (b) flooding the lane with re-acks of a state you already verified.

## 1 · A report is a claim; verify on the wire before you ack

Never relay or ack a lane's "PR open / head X / not draft" from its prose. Read the API first:

```bash
gh pr view <n> --repo asimov-agent/llgenie \
  --json number,state,headRefOid,headRefName,baseRefName,mergeStateStatus,mergeable,isDraft,title
```

Quote the ids you verified (head sha prefix, mergeStateStatus, base). A report without a branch and a
run id is not a report.

## 2 · When the claim is about a DESIGN, read the artifact, not just the PR metadata

"It's a thin Dockerfile", "prebuilt:true", "install_nsteps:0" are claims about file CONTENT. Verify by
reading the file at the PR head, not the title:

```bash
git -C <canonical> fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch> -q
git -C <canonical> show refs/remotes/origin/<branch>:<path>
```

Engine params nest under `variants` — `variants.rocm.prebuilt` / `variants.rocm.base`, NOT a top-level
`rocm` key. A top-level lookup returns `None` and looks like a failed claim; navigate `variants.{cuda,rocm,cpu}`
and print the real booleans before judging.

## 3 · Ack a substantive report once, concretely

One ack per report: state what you verified (head sha, base, the artifact line) and your position
(on the board, not merging, owns-branch-through-review). Do not re-derive the same facts on every
follow-up message about the same PR.

## 4 · A `[no reply needed]` or repeated-state FYI gets intentional silence

When a lane message is marked "[no reply needed]", or is a final-state relay that repeats a state you
already verified and acked, end the turn with the silence token (`[SILENT]` / `NO_REPLY`). Do NOT re-run
`gh pr view`, do NOT post another ack — a string of identical "#2274 @ f62b0557, waiting on runner"
relays is one verified fact, not five tasks. Re-acking a routine FYI only adds noise to the lane and
the board.

## 5 · Keep the split visible when one PR clears half a red

When a fix removes one dimension of a multi-part gate red (e.g. a thin rocm cell clears the rocm 404 but
cuda stays `prebuilt:false` and still 404s), state the split explicitly on the tracking issue so review
does not believe one PR clears the whole class. Route the remaining half to its owning lane as a separate
deliverable.

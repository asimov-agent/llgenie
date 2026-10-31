# Coordinating work on a shared (multi-lane) branch

When two lanes fill ONE PR / ONE branch — the classic shape is a producer lane owns the
engine-build side and a CI lane owns the consumer side — these rules keep the vehicle intact.

## Start from the live head, never the head you remember

Re-read `gh pr view <n> --json headRefOid` AND the file list before touching anything, and state
the head you read. A multi-lane branch moves fast: the head shaped in the morning is two commits
along by the afternoon, each from the other lane. Planning against a remembered sha is planning
against a tree that does not exist anymore.

## Adapt ADDITIVELY onto the live head, never reset to a remembered one

Deviation-based rebase: `git fetch <remote> <branch>:refs/remotes/<tmp>` then rebase/merge HEAD
onto that live ref. Resetting to the earlier sha you remember DROPS the other lane's commits —
that is a force-push-under-dispute and a coordination failure, not a cleanup.

## Grep the live branch before re-adding anything you planned

If your prepared delta adds a mechanism (a guard pin, a make target, a roster row) and the other
lane may have committed it since you planned: `git show <live-head>:<path> | grep -c <symbol>`
and skip it if present. Re-adding it is a double-pin — the gate runs twice, or the duplicate
reds the very check you added to protect.

## A same-named symbol is not the behaviour you planned

A file's content can change meaning mid-coordination: the other lane reshapes the same-named
make target to a DIFFERENT recipe, or repurposes the file entirely. The symbol existing is not
the behaviour you designed against — re-read the live hunk before wiring your side to it.

## When you cannot push yet, hand the diff; when you can, confirm no double-capture

Holding a branch for a calibration (e.g. the owner's direct word) is fine — but keep the prepared
delta uncontested by handing it verbatim to the authoring lane and say you will not push a copy.
A prepared delta that is superseded on the branch is NOT "mine to push anyway"; pushing it is a
double-build that defeats the single-vehicle coordination the multi-lane PR exists to preserve.

**A push gate blocks PUSHES, not analysis — a lane parked on one is not idle.** An owner-word gate
forbids writing to a shared branch another lane owns; it does not forbid read-only measurement,
issue filing, comments, or a **committed-but-unpushed local branch**. So when the gate holds, do not
report "standing quiet, nothing until the owner speaks" and stop: produce gate-free work — measure
the defect with `file:line`, post a reviewable **diff in an issue comment** (an artifact, not a
claim, it crosses no gate), or materialise the fix as a commit on a local branch (recoverable,
still unpushed). Only the final `git push` waits. Stating the gate as "no work" instead of "no
writes" turns a disciplined lane into an idle one; name the gate's true scope (writes to a branch
you do not own) and keep doing everything inside it.

## The scope can change under you — verify, then absorb

An owner direction mid-coordination can flip what the branch is FOR (e.g. "the engine build/test
does not live in ci.yml at all" reverts the whole consumer half). Re-read the live file list to
see what actually landed, and re-scope your prepared delta or drop it. Never keep pushing the
old shape against a re-directed branch.

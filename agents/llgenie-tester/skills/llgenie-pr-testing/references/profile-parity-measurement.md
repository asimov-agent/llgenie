# Profile parity: measure read-only, fold live→tree by issue+PR

Before any work on a lane's own profile files, the question "is the tree copy the same as the running profile?" is answered with two READ-ONLY commands. Never with a sync.

## The two measurements

```bash
make sync-agent-profile PROFILE=<profile> CHECK=1     # per-file: same / DIFFERS / TRUNCATED?
make tester-fold-live PROFILE=<profile>              # blobs: same / DRIFT / LIVE-ONLY / live-missing / mid-write
```

Both are report-only and exit non-zero when the profile is not byte-identical to the tree. That exit code is the answer, not a failure to fix. Report the counts, e.g. `5 same, 4 drifted, 0 live-missing, 6 live-only, 0 mid-write`.

## What each verdict means

| verdict | meaning | who fixes it |
|---|---|---|
| `same` | byte-identical blob | nobody |
| `DRIFT` | both copies exist, different content | the larger/newer side wins — see direction below |
| `LIVE-ONLY` | the running profile carries a file the tree lacks | fold live→tree (issue+PR) |
| `live-missing` | the tree carries a file the profile lacks | deliver by a tree→live sync once the tree is not truncated |
| `TRUNCATED?` (CHECK=1) | the tree copy is SMALLER; a sync would delete live behaviour | re-copy tree from live, then sync |

The direction rule: **the live profile is authority and is never trimmed.** A live-only file or a live-longer file is a tree-side hole, closed by copying live content into `agents/<profile>/` through an issue + PR — never by syncing tree→live.

## Never `COPY=1` or `FORCE=1` without a line-subset proof

The fold tool has a copy mode and the sync tool has a force mode; both are destructive in a way the summary line hides:

- `make tester-fold-live PROFILE=<p> COPY=1` **overwrites tree files with live content wholesale.** It does not merge. Every tree-only line in those files is destroyed — measured shape: 31 tree files overwritten and 72 tree-only lines erased across 12 files (a SOUL, a 35-line skill body, several references), with the drift report still reading "folded successfully".
- A plain `make sync-agent-profile` (no CHECK) **replaces the live profile** with the tree copy — which is why CHECK=1 exists: `TRUNCATED?` means the tree is the lossy one.

The only safe copy is preceded by a line proof: extract the tree file's lines and the live file's lines, and confirm the destination is a superset (`comm -23` of tree-only lines is empty) before writing. Without that proof the operation is a guess that eats prose nobody can restore except by re-reading the live profile.

Recovery if a copy already ran: `git checkout -- agents/<profile>/` restores the tree from HEAD, then re-run the read-only checks and confirm the tree is clean vs HEAD before reporting.

## Reporting shape

Give the raw numbers with the method that produced them, and name the direction each drift owes:

```
CHECK=1: 4 of 9 differ; 3 would SHRINK live (SKILL.md −143 b, <ref> −1,647 b, <ref> −2,402 b)
fold-live: 5 same, 4 drifted, 0 live-missing, 6 live-only, 0 mid-write
live-only: <file>, <file>, … → fold live→tree by issue+PR
```

A live-only reference that the SKILL links will red `skill-reference-missing` once the tree is checked, so the fold is owed even when the drift looks cosmetic.

## Two shell traps in this measurement

- **Do not pipe when you need the exit code.** `make <target> | tail` makes `$?` the exit of `tail`; a refused check then reads as success. Run the target unpiped (output is truncated by the harness anyway) or capture `PIPESTATUS`.
- **`~/.hermes/profiles/<p>/skills/` is not the same tree as `agents/<p>/skills/`.** The first is the running profile the agent loads; the second is the repository copy CI validates. Editing one does nothing for the other, and comparing their sizes by eye is how a "synced" claim gets made about the wrong file.

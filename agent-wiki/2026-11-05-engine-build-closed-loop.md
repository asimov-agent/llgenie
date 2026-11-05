# a failed `make build-engine` cell is a five-step closed loop the lane is OWED

## Background (issue #1772, owner requirement 2026-11-05)

The engine-improver lane's documented behaviour made "read the failing log" a hard rule (SOUL):
quote the error line before any claim — and knew the narrow cell dispatch (`gh workflow run
395994204 --ref <branch> --field engine=<id> --field arch=<backend>`) and the leg-classification
table (`publish-run-adjudication.md`). But none of the three wired **log → verdict → fix → single-cell
push → GHCR-confirm** as ONE mandatory sequence, so a red engine-build cell could be triaged (classified
+ tracked, e.g. the #1745 13-red pass) without any lane being owned for the rebuild-and-republish
follow-through.

## The owner requirement

On a failed `make build-engine`, the lane does the full closed loop as one sequence:

1. **read** the failing leg's OWN log — run id + job id + head sha — and quote its error line;
2. **classify** the failing leg per `publish-run-adjudication.md` — a `build-engine` failure = image
   never built (real publish-path defect); a verify-gate red = `push-engine` SKIPPED → tag missing
   (acceptance gap); a `push-engine` success with a later `install-leg` red = image IS in GHCR,
   verify-class only — a `conclusion` is a verdict, not a cause;
3. **fix** that cell — its params / Dockerfile / install-leg, never a sibling's cause generalized;
4. **re-dispatch the SINGLE engine×arch** — `gh workflow run 395994204 --ref <branch>
   --field engine=<id> --field arch=<backend>` — with `push=true` only when the fix is a publish-path
   change; **never a full `engine="" arch=""` sweep** — and quote the new run id;
5. **confirm the fresh GHCR tag exists before calling the cell resolved** — probe
   `scripts/ghcr_publish_probe.sh <leaf> <tag>` → `PUBLISHED` — a missing tag is indistinguishable from
   never-built.

## What changed

- `agents/llgenie-engine-improver/SOUL.md`: a lane rule adding the five-step sequence (read-log →
  classify per `publish-run-adjudication.md` → fix that cell → single engine×arch push → GHCR-confirm),
  explicitly gating `push=true` on a publish-path fix and the narrow dispatch AWAY from a full
  `engine="" arch=""` sweep.
- `agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md`: the loop's mechanics rule,
  citing the existing `publish-run-adjudication.md` and `engine-build-proof-dispatch.md` references so
  the sequence is one explicit rule rather than scattered facts.

## Acceptance

`make check-docs` + `make lint` green; change-note + fragment per #1123; PR (docs/agents only) closes
#1772.

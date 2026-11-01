# tester lane live→tree fold, round 6 (2026-11-01)

Versioning the tester lane's live→tree drift at `afffc14c` (#1276's merge). Live accreted one
conservation/sequencing lesson in two files. Pure accretion (nothing trimmed); byte-copied live→tree
and re-hashed. Also re-read both files twice at copy time to prove they were not mid-write
(`a3b1e053`→`296adb10066d` SKILL; `4509c08f`→`f7a034a4ad0d` versioning — stable across reads).

## The folded lesson

Keep **ONE fold vehicle in flight** — do not race live. The delta is monotone accretion (live never
shrinks), so a follow-up opened while the current fold is open or unmerged copies a superset of what
the first vehicle already carries: the second lands a duplicate, burns a matrix, and yields two PRs
whose diffs overlap. Sequence strictly — land (or see merged) the existing fold, re-enumerate live,
then open the next vehicle for whatever accrued since. "Live moved again" is not a reason to open
another PR; it is the expected state the next round starts from, and waiting costs nothing because
nothing is ever deleted. Before copying, prove the live file is not mid-write: hash, wait, re-hash.

This rounds' own cadence exercised the lesson in reverse — #1260/#1270/#1272/#1276 each landed a fold
a step behind live because the owner merges doc-folds fast; the correct response was to land each and
fold the next delta, which is what this single vehicle does now.

## Proof at the committed head

`SKILL.md` `296adb10066d == live`; `agent-profile-versioning.md` `f7a034a4ad0d == live`; 3 other
reference files + SOUL unchanged byte-for-byte; `make changes-index` regenerates `CHANGES.md`.

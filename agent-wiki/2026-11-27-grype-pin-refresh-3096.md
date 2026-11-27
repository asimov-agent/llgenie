# Grype pin refresh to 0.122.1-r0 (issue #3096)

PR #3105 on branch `agent/issue-3096-grype-pin`, cut from `origin/main@412b84f02`.

## Verified against the spec (`openspec/changes/grype-pin-refresh-3096/`)

- `containers/scanners/grype/Dockerfile:18` now pins `ARG GRYPE_VERSION=0.122.1-r0`; the shared
  `containers/scanners/digests.json` grype entry was regenerated with `make scanner-digests`
  and names the same version, the Dockerfile content-hash tag `ce32a3411abe` and the published
  manifest `sha256:38b348a165abaf1386990e752764766db54e4233e5547578c868d00dd13a5de8`. No
  per-scanner `digests.json` was created.
- `make scanner-freshness` rc=0 against the live Wolfi x86_64 APKINDEX: 4 pins checked, none
  lagging the newest published build beyond the 7-day grace. This was the red from #3096.
- `make test-scanner-image SCANNER=grype` rc=0 prints `grype 0.122.1` from the rebuilt image;
  `make check-scanner-images` rc=0 accepts all four inventory entries; `make check-security-scan`
  rc=0 accepts the bumped pin against the unchanged baseline.
- The image was published through the scanner-pipeline build+push path before the digest was
  pinned; the gate's `image_digest` requirement is satisfied by a real registry manifest, not a
  fabricated sha.

## Key decisions

- The grace window and the freshness gate were not touched: the published pin moved instead of
  the alarm being muted.
- The docs note and changes row are the companions the tree owes for a behavioural pin change
  (issue #1123); the agent instruction files of every lane were left alone.

## Status

- Ready for review at head `4577eb998d712ffe808b0220bcad25224034486e`: `make -s check-docs` rc=0
  (992 fragments indexed; census referent `d43b1df8` is an ancestor of that head), and this note's
  `CHANGES.md` index row is canonical — `make changes-index` produces no diff. The earlier
  `04b01ec97b76` measurement is history, not the branch's current state.
- `guard` is red only on #3096's unticked acceptance boxes (verdict-gated write-back, #1644), owned
  by the reviewer lane; the note-and-index half is complete. Never merged or armed.

# 2026-11-17 — agent-test-controls-2883 (issue #2883)

Shipped the `llgenie-pr-merge-conflict` lane's two detector controls into the lane tree.

- Source: live profile root `scripts/` (rows 12-13 of the #2880 LIVE-ONLY classification, census head
  `585b03dd740c121564190f86987f9bac89f4e796` of PR #2882).
- `test-dirty-detector.py` sha256 `5f281cb555f85c26931929ff53be192a4c0433f7eb5c6841829ce4240d0ce5f3`
- `test-tally-delta.py` sha256 `e26f04cd9565485f9d459bdf85ee357ed56071fa56da0954740092ae2cdbfb52`
- Both copied byte-identical (live side untouched, fold contract from #2878/#2882).
- Host-side proof at the tree copies: detector control 4/4 PASS rc=0; tally control 16/16 PASS rc=0
  (stub-`gh`, synthetic cases only — no network, no GitHub state touched).
- Hyphenated names keep the controls out of pytest collection; they load their subjects via
  `HERE / dirty-detector.py` / `HERE / tally-delta.py`, so they work from the lane tree directory.

Verified: census `42 same, 0 drifted, 0 live-missing` at the head; sync CHECK byte-for-byte clean;
test_agent_profiles green; check-docs green; openspec-validate green; preflight OK.

Status: PR opened against #2883; closes on merge.

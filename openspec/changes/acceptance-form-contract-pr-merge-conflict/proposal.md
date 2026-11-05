# Proposal — per-lane acceptance-criteria form contract for llgenie-pr-merge-conflict (#791 / #1796 / #1812)

The #791 per-lane acceptance-criteria form-contract fleet rollout requires every
affected lane's skill to state the rule verbatim: every issue a lane files AND
every PR body it opens carries a `## Acceptance criteria` section with each
criterion a `- [ ]` markdown checkbox — one per provable outcome; a criterion a
reviewer cannot tick is not one (#745).

This lane (`llgenie-pr-merge-conflict`) skills file under `agents/` did not yet
carry the contract on main at `dde5c9ec`, which is why the reviewer's #1804
verdict left #1796 #1 unticked (6/6 gate gap).

No product code changes — the diff is skill-text + change-note pair only.

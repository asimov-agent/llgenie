# own-domain audit contract for the rebase lane (#1852)

The `llgenie-pr-merge-conflict` lane's empty-queue own-domain audit (#1245) gained a codified measurement
contract (`references/own-domain-audit.md`): every claimed head/base is re-read from the API at the moment
of the claim (never a stale prior record), every base in the last N rebases is checked as an ancestor of the
*current* `origin/main`, a finding's own witness is read from the changed PR's live `check-runs` conclusions
(never a relayed "passed"), and findings file as refined `agent:implement` issues — the audit never fixes
in-pass. The two defect classes it now guards: citing a head as live without re-measuring it at the claim
(issue #1852 trigger: `4c3ac6f7`/`bb0eb516` cited ~20 min after the sweep landed `c139ca97`/`888e879a`), and
citing a vehicle as "passed" on a stale witness instead of its live `check-runs`. Issue: #1852.

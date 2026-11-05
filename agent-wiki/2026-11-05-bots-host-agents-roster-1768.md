# docs/BOTS.md host-agent frame sources the roster from agents/manifest.json (#1768)

`docs/BOTS.md` §host-agents said "The two **host** agents" and showed an example `agents/` tree with
only `llgenie-planner` and `llgenie-issse-implementer` plus `manifest.json`. The tree on main grew to
**13** profile directories under the same #791 mechanism (architect, business-analyst,
ci-pipelines-maintainer, documentation-maintainer, engine-improver, issse-implementer, planner,
pr-merge-conflict, pr-reviever, product-manager, security, status-keeper, tester), and
`agents/manifest.json` lists the same 13 — so a reader concluded the other fleet bots' behaviour was
not tree-versioned when it is.

## The fix

The prose now states the true roster (13, sourced from `agents/manifest.json`) and names
`make agent-profiles-report` (and `manifest.json`) as the authoritative listing — never a prose
sentence. The example `agents/` tree is explicitly captioned as an illustrative two-of-N sample, so
it cannot be misread as the complete set. Doc-only under `docs/BOTS.md`; no script, test, workflow
or agent behaviour touched.

## Verify

At the head sha: `agents/manifest.json` `profiles` = 13 and `git ls-tree --name-only <head> agents/`
= 13 `llgenie-*` dirs, so the stated count and roster match the tree. `make lint` and
`make check-docs` green at the head.

# Rebase lane: version live `references/pitfalls.md` into the tree

Closes the last `llgenie-pr-merge-conflict` live->tree drift row from #961 / #1060 (does **not** close
those issues).

`#1147` (merge `c7722643`, 07:57Z) carried the live skill state and cleared 11 of the lane's 12 drift
rows. The lane's own `llgenie-dirty-watch` cron then appended 18 lesson lines to the **live**
`references/pitfalls.md` at 08:40:37Z — duplicate-vehicle detection via per-file
`git diff origin/main:<f> <head>:<f>` content counts rather than ancestor/path presence (the #1084
lesson: a skill PR whose directory shipped long ago reads VACUOUS under an ancestor check even when its
paths are trivially on main, because the ancestor check says nothing about the content). Because
`make sync-agent-profile` is one-way (tree -> live), that live write can never return to the tree, so
`check_agent_profiles.py` re-reports the file as `live-longer`.

Verified live is a clean superset of main (`comm`: 0 main-only lines), so this is a pure union — no
tree line is dropped.

The recurrence is tracked as #1156: until the dirty-watch cron stops writing skill lessons to the live
profile and lands them via PR instead, this row reappears after every clearing PR.

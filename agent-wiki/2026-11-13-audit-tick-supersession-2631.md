# acceptance-tick supersession sweep (issue #2631)

Issue #2288 (PR #2630) made NEW acceptance ticks honest; the append-only
`<!-- AUDIT-2288 -->` addenda recorded that 178 already-ticked criteria across
46 closed issues cite runs whose live conclusion is not green (41 distinct
runs: 40 failure/cancelled, 1 unreadable 404). The addenda record the scar;
they do not resolve the denominator.

Live re-measure by the repo tool on 2026-11-13: 1308 closed issues, 311 ticked
criteria citing `run=<id>`, 172 unsuperseded stale criteria across 44 issues,
40 cited runs (39 red at 39 distinct heads, 1 unreadable 404 `43073777356`).
`head_green` shows the 39 distinct red heads carry ZERO completed/success runs
of the CITED workflows (`gh api .../actions/runs?head_sha=` per head: 3 heads
have no green run at all, 36 carry green runs only for unrelated workflows —
a same-head green of another workflow never re-proves the tick), so a
same-head green re-tick cannot be minted honestly for those criteria. The one
criterion whose cited run was unreadable (#2472, run 43073777356) is 404 and
its cron has since been re-shaped (`1 6 15 * *` is no longer in any workflow;
semgrep-rules-refresh now schedules `17 6 15 * *`), so no fresh run honestly
replaces that sentence either.

Decision (OpenSpec `audit-tick-supersession`): `scripts/audit_acceptance_ticks.py`
carries the corrected audit as a repo tool — `audit` re-measures the whole
closed-issue corpus (GraphQL paging, live run states, per-head green survey)
and excludes criteria covered by a machine-readable `<!-- SUPERSEDE-2288 -->`
note; `render_supersede_note` is the one renderer for the note (it quotes each
criterion, names the cited run's measured conclusion, and states the per-head
survey); `post` posts it append-only with marker idempotence. Zero issue-body
re-ticks were minted: every stale tick resolves by supersession, ticks stay as
written, and `audit` exits 0 only when zero unsuperseded stale ticks remain
(`make audit-ticks`).

Current status: sweep executed on the wire — 44 supersession notes posted (one
per issue, 172 criteria quoted, 171 head-survey lines), re-audit exits 0 with
0 stale / 172 superseded; tests (8) + lint green locally; PR carries the
three-mirror acceptance block and issue #2631 is ticked on the wire.

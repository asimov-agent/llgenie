# A disarm is a decision, not an absence (#1106)

## Why

`autoMergeRequest` is a single writable field with no history. From any later pass, "not armed" reads
identically whether nobody armed it yet or the author stopped it on purpose, so the orchestrator tick
re-armed a PR whose author had deliberately disarmed it twenty-six seconds earlier (#1084, 21:45:02 →
21:45:28). The wrong rule would have merged into a skill other lanes read had a review gate not held it.

## The fix — one expression, one central write

The only code that writes `autoMergeRequest` is `scripts/arm_auto_merge.py::arm()` → `gh pr merge --auto`
(`:80`), reached from the `unarmed()` selector at `:59` — `not pr["autoMergeRequest"]` treats "no merge
intent" as "owes arming" with no memory. A deliberate disarm becomes a **comment** whose body contains
`disarmed: <reason> — re-arm when <condition>`; a later `re-armed:` comment clears it. `unarmed()` gains a
veto: a PR whose latest decision marker is a disarm is **skipped**, never `gh pr merge --auto`'d, and the
report splits `armed N, skipped M (author-disarmed): [ids]`.

The comment list is the field with history; `autoMergeRequest` is the one with none. This reuses the
comments-API idiom `check_holds.py` already ships, so no schema change.

## Verified, not claimed

`pytest tests/test_arm_auto_merge.py` → 10 passed. Negative control run: force `disarm_state()` to return
None → `test_a_deliberately_disarmed_pr_is_skipped_not_rearmed` FAILS (1 failed, 9 passed); restore →
10 passed. The three controls pinned: disarm + green + unarmed → skipped (report names the PR); a later
`re-armed:` clears the veto; no marker → still armed (a mid-body `disarmed` substring that is not a marker
must not veto).

## The one-character trap this issue exists to teach

The marker tuple was always ordered `(created_at, kind, text)`. The bug was the **unpacking** —
`kind, _, text = markers[-1]` bound the **timestamp** to `kind`, so `kind == "disarm"` could never be true.
The fix is `_, kind, text = markers[-1]`; the description must say "the unpack bound the timestamp to
`kind`", not "the tuple order was wrong". Issue: #1106 · Evidence: #1084 comment 6534272705 · Refs #912.

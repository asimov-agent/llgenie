# A PR closes the issue it implements — the closing rule loses its loophole

## Why

`AGENTS.md` states the closing requirement with an escape hatch: "If the PR does not close an issue,
still end with the issue reference so the PR ↔ issue link is never ambiguous." That reads as permission
to ship a PR that implements an issue without closing it. Measured on `main` (`4d999e3`), **13 of the
last 38 merged PRs carry no closing reference at all** (`gh pr view <n> --json closingIssuesReferences`
→ empty): `#258`, `#290`, `#266`, `#274`, `#268`, `#284`, `#283`, `#282`, `#280`, `#278`, `#267`,
`#259`, `#255`.

Two of those are the sharp cases. **#290** implemented the fix-bot half of issue **#279** and closed
nothing — #279 is still `OPEN`, its remaining half tracked only in prose inside a PR body. **#321** was
**closed by hand** at `2026-10-16T02:47:40Z` with **no implementing PR**, and its defect still
reproduces on the current tip: run `38841759439` on `4d999e33`, `failure`, **0 jobs**.

The cost is exactly what this repo's issue → branch → OpenSpec → PR pipeline exists to prevent: an
issue's state stops being evidence about the code. An issue closed with no PR reads as "done" while the
defect it names is still live, and a PR that closed nothing leaves its issue open forever.

## What changes

- **`AGENTS.md`** — the closing rule loses the loophole and states its three cases explicitly: a PR that
  implements an issue MUST close it; a PR that implements only PART of an issue MUST NOT close it and
  MUST name what remains as a linked work item; an issue MUST NOT be closed by hand while a PR
  implements it. The "still end with the issue reference" sentence is removed, since it is the loophole.
- **`scripts/check_pr_hygiene.py`** — the `agents-mandate` check currently asserts only that the mandate
  *heading* exists. It is extended to require the closing-rule text as well, so deleting the rule is a
  red `ci-unit`, not a silent edit. The mandate is split into named constants (heading, closing rule)
  and each is checked on its own.
- **`tests/test_pr_hygiene.py`** — a fixture case per new requirement: an `AGENTS.md` that carries the
  heading but dropped the closing rule fails, and the real tree passes.

## Impact

A PR that implements an issue now closes it as a matter of rule *and* gate; the guard reads the closing
rule in `AGENTS.md` the same way it reads the message mandate, so neither can be removed without turning
CI red. The three cases remove the ambiguity that produced #290 and #321.

## Not covered

- **No gate reads a live PR.** The guard reads the repo's own files; whether a merged PR *did* close its
  issue is only visible through the API. Reporting that is a separate work item — **#325** — named in the
  PR's `Not covered` per AGENTS.md, never as prose in this change.

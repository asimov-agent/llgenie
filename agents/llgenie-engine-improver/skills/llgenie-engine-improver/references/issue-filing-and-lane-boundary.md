# Filing an engine-lane issue, and where detection ends

## Shape gate — validate with the repo's own module

Before `gh issue create`, run the body through `scripts/issue_body.py` instead of eyeballing it:

```python
import sys; sys.path.insert(0, "scripts")
from issue_body import headings, missing
headings(body)  # -> ["Problem", "Why it matters", ...] found titles, in file order
missing(body)   # -> [] when conformant
```

There is no `problems()` helper; `headings` + `missing` is the whole API. Required six sections, **Technical last**: Problem / Why it matters / How we fix it / Benefit / Acceptance criteria / Technical.

Then:

```
gh issue create --repo asimov-agent/llgenie --title '<type>: <what> — <gate> reds' \
  --body-file <body> --label bug,agent:implement
```

Read the returned number back (`gh issue view <n> --json number,state,labels`) and post the measured evidence as a claim comment on the issue — the numbers in the body must come from a command actually run in this session.

## A dispatch is not automatically a PR — classify the issue first

A planner dispatch whose template says "done = ready-for-review PR that closes #N" does not mean every
issue in the batch yields a code PR. Classify each before opening a branch:

- **Code vehicle** — the fix is a change THIS lane can make and own → open the PR, arm auto-merge.
- **Monitor** — the deliverable is the cross-cell / cross-run comparison, posted as an issue comment
  (it satisfies "collect + compare + classify" ACs); the monitor closes when the root fix lands, so do
  not open a docs PR just to have one.
- **Gated** — the fix depends on another lane's build/merge (a pin cannot publish until the build
  greens, an issue forbids silent re-pin) → post the verification evidence, state **stays OPEN, gated
  on #X**, and do not self-close or hand-repin.

Forcing a code PR on a monitor/gated issue misrepresents ownership and hands the next lane a stale
branch. Report per-issue status to the planner (PR # for the vehicle, evidence-comment sha for the
monitor, "OPEN gated on #X" for the gated one) rather than a blanket "3 PRs".

## Lane boundary: detect vs publish

- `make check-engine-launchers` reporting `N ok / 1 stale / M missing` — the **`stale`** row is the real red; `missing` rows for an arch (sglang/tensorfold on cuda) are legitimate/informational.
- Reproducing it: `make engine-launchers ENGINES=<x>` prints the exact failing `docker pull ghcr.io/asimov-agent/llgenie/<engine>:<pin>-<params>-<backend>` (`FAIL <engine>/<backend>: not published`). That output **is** the finding — quote it verbatim.
- **Detection is this lane's; publishing the image is the pipeline lane's CI-publish matter.** File or keep the tracking issue, hand over the one-line failing pull, and stand down: no fix, no repin by hand, no local image build.
- If the planner dispatches a publish fix to this lane, that is a mis-route — say so plainly and hand back the measurement rather than picking up the build.

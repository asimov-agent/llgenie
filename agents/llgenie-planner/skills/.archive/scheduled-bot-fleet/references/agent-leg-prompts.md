# The agent-leg prompt as a contract

A bot leg that calls a model runs with **no user attached**: one prompt in, one exit code out. The prompt is
therefore the whole contract — what the leg may touch, what it must write, and what it must never wait for.
Treat it as code: one make target per leg, one test that reads it.

## The unattended rule (put it in every leg)

```
UNATTENDED: this run has no user - NEVER ask a question and never wait for input. If a decision is
open, take the path that needs none (a refine with its REFINED/REASON, or a close with cited EVIDENCE)
or make the safest reversible choice and state it in your output; a question fails the run.
```

Why it is mandatory rather than nice-to-have: `--yolo` auto-approves **shell commands** and
`--accept-hooks` auto-approves **hooks**, and neither answers the model's own `clarify` tool. With no TTY the
run prints

```
Input required; detached without cancelling. Resume this session interactively.
```

and exits **3**, leaving the tree untouched. Every downstream message then lies by omission: the leg reports
"changed nothing", "produced no implementation", or a budget error, and the reader starts with the data, the
API key and the model alias — three things that are fine.

Also put it in the shared rules file (the one a repair loop hands the agent) when the repo has one, and give
each prompt the same sentence so a new leg cannot be added without it. Past two legs, stop repeating it —
move it into one preloaded skill (next section).

## Where the contract lives: a project skill

A leg's rulebook inline in the `Makefile` is the shape that rots: N copies of the same rules, a prompt that
grows back to 4 KB the moment someone adds a clause, and nothing that can tell a leg which LOST its contract
from one that never carried it. Replace it with Hermes **project skills**:

```
.hermes/skills/bot-unattended/SKILL.md    # the paragraph above, written ONCE
.hermes/skills/<leg-family>/SKILL.md      # one per family: search, implement, review, fix
```

- Frontmatter `name` MUST equal the directory name (a mismatch is not resolvable by `-s`), and the body
  carries `## Inputs` / `## Output` / `## Rules` — those three sections are what a gate can check and what
  the model reads first.
- Every leg runs `hermes -s <skill>,bot-unattended` and its inline prompt becomes a POINTER plus that run's
  parameters: the input file (`issue.md`, `qa-report.txt`), the verdict grammar, the per-backend keywords, the
  macro expansions the Makefile owns. Keep the parameters inline; move the RULES.
- A pointer prompt is ~300–900 characters. The search legs stay near 2 KB because they carry their keyword
  list and macro expansions — that is a parameter, not a rulebook.

### Registration: an unregistered directory is a leg with NO contract

`hermes -s <name>` resolves skills from the Hermes home and from `skills.external_dirs`, so the checkout's
`.hermes/skills` has to be registered in the container's home at setup time, and READ BACK:

- Write it through the CLI (`hermes config set skills.external_dirs '<json array>'`, `hermes config get` to
  read), not by editing `config.yaml` with a YAML library — a repo whose `requirements.txt` is
  `jsonschema` only has no PyYAML, and the CLI is already installed in every image that runs a leg. Pass the
  home with `HERMES_HOME=<path>` (it is honoured) so the script is testable against a temp home.
- The value must be a real LIST: some versions store a JSON literal as one opaque string, and the loader then
  treats it as a single non-existent path. Reading back through the CLI is what proves the shape.
- Idempotent (register twice, one entry), `--check` verifies without writing (exit 1 = not registered),
  a missing CLI or a missing directory is a loud non-zero — never a skip.
- Wire it into `setup` and run the read-back check in the SAME recipe: the image build runs setup, and the
  repo is mounted at the same path at run time, so a build-time registration is the run-time one.
- **Prove it in the real image**, not just on the host: rebuild the agent image and run
  `hermes skills list --source local` inside it, expecting each skill to show as an `external` source. A
  local `hermes skills list` on the host proves the HOST's config, which no bot uses.

### The gate (`check-agent-skills`, in the lint stage)

One script, `check` + `report` modes, exiting 1 on any finding:

| finding | why it matters |
|---|---|
| a `hermes -z` leg preloads nothing | its rules are inline again |
| a leg names a skill that does not exist | it runs with no contract at all and reports success |
| frontmatter `name` ≠ directory | `-s` cannot resolve it |
| a skill lost `## Inputs`/`## Output`/`## Rules` | the contract has a hole |
| a recipe inlines the unattended sentence | the duplication the seam removed |
| a leg's prompt exceeds the pointer budget | the rules crept back in |
| the Makefile lost the seam block or the registration target | the seam could be deleted silently |

Name the one documented exemption (a routing-smoke script that calls `hermes -z` with no contract to carry)
in the script and fail when that file disappears, so "scanned" and "skipped" stay distinguishable.

## Exit-code map the workflow must honour

| code | meaning | the failure step should say |
|---|---|---|
| 0 | the leg ran and wrote its output | success / no-op |
| nonzero (other) | the model or the tooling failed | the real error tail, plus the leg's own check |
| **3** | **detached: the agent asked for input** | "the agent asked for input (detached, rc=3) — an unattended leg must decide without a user" |

Order the `rc == 3` branch **before** the generic "changed nothing" message: that message is true but
misleading, and the reviewer reading the run cannot act on it. Build both texts from the state you read
(the rc output), never from a reason variable that is unset on the success path.

**rc=3 is a failure only when the tree is CLEAN.** The preloaded contract makes an early question unlikely,
not impossible: a model can still call `clarify` once, and measured it did so at the END of a 30-minute leg,
after implementing — so the exit code said "nothing" while the checkout held the whole change. Give the job a
step that reads `git status --porcelain` after the leg (gitignored scratch is invisible to it): a dirty tree
is SALVAGED (commit, push, open the PR, `::notice::` the exit code), a clean one stays red. Same family as
the 120-minute-cap loss: the work is the deliverable, the exit code is a diagnostic.

## Shape of a leg prompt

1. **Read the input file first** (`issue.md`, `fix-report`, the failed run's log) — name it and say it is the
   specification, not background.
2. **Decide, then write ONE file.** A decision leg writes its verdict to a fixed path and is told explicitly:
   do not comment on the issue, do not push, do not open a PR — the deterministic runner applies the verdict.
   That keeps the model out of the write path that the bot owns.
3. **The hard rules, numbered**, one sentence each: what may change, what must not (worktree, commits, main),
   which gate to run, which artefact to leave (`pr-body.md`, `findings.md`).
4. **The unattended rule last**, so it is the final thing read.

## Testing the contract

- Read the REAL files in the test — the Makefile target, the rules file, the workflow — and assert the rule
  and the `rc == 3` branch are present, with the `rc == 3` branch ordered before the generic message.
- Count the prompts (`assert makefile.count("UNATTENDED: ") == N`) so a newly added leg fails the test until
  it carries the rule, instead of silently shipping without it.
- Assert against target names that exist: list the `_name:` recipe headers first rather than assuming a
  target name (a guessed `_issue-bot-refine` when the target is `_issue-refiner` is a green test that never
  reads the prompt).
- **Assert phrases that survive line wrapping.** A rule moved into a markdown skill wraps across lines, so
  `"before any code" in skill_text` fails while the rule is plainly there — either keep the asserted phrase on
  one line in the skill, or compare on normalised whitespace (`" ".join(text.split())`). The same trap hits a
  test that pins prompt text you later reflow.
- **Slice the WHOLE recipe, not the `-z` line.** A recipe is two lines (the prompt, then the flags); a test
  that takes `mk.split("_fix:\n")[1].split("\n", 2)[1]` sees only the prompt and reports the `-s` preload as
  missing. Use a regex over the tab-indented block.

## What not to do

- Do not retry a detached run and call it flaky: nothing was flaky, the model asked a question.
- Do not add a second, shorter prompt "for the retry"; extend the one the leg runs.
- Do not let the model's own summary be the only record of a decision — the verdict file plus the runner's
  marker is what a later run can read.

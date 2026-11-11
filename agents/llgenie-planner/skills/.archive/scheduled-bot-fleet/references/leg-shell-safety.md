# Shell safety for make-invoked bot legs and probes

The failure mode these all share: the bot reports "agent failed" or "binary missing", the run looks like a
model/engine problem, and the real cause is the shell text make handed over.

## 1. `$(call macro,…)` splits on literal commas

GNU make splits a call's arguments on commas in the **unexpanded** text, so

```make
$(call scrubbed_run,$(RUNTIME) run … bash -lc 'hermes -z "…" -s a,b --yolo')
```

passes `$(1)` = everything up to `-s a`. The rest of the command — including its closing quote — is dropped,
the shell dies with `unexpected EOF while looking for matching '` and exits 2 **before the agent starts**.

- Exposed shape: a leg that inlines its whole command (it must when the tree's own `Makefile` is the file
  being repaired). Legs that run a `_<leg>` target (`bash -lc 'make _refiner'`) never see it.
- Fix: give the list a variable — `LEG_SKILLS := a,b` then `-s $(LEG_SKILLS)`. A variable *reference*
  carries no comma, so the call splits correctly and expands to the list.
- Diagnose: `make -n <target>` and count single quotes (odd = truncated); the printed command should also
  contain the full list.
- Guard: derive every target whose recipe calls the macro from the Makefile, expand each with `make -n`,
  and fail on odd quotes or a list that lost its second entry. A checker that parses legs **textually** must
  first expand simple `NAME := value` assignments, or it reports `$(LEG_SKILLS)` as a missing skill name.

## 2. `pipefail` + an early-exiting reader = 141, read as "missing"

Every leg step typically runs under `set -euo pipefail`. A reader that stops at the first match
(`grep -q`, `grep -m1`, `head -1`) makes the writer take SIGPIPE, and the pipeline's status is
128 + 13 = **141**. A probe then declares a healthy binary missing and the reader chases the binary.

- Safe readers (they consume to EOF): plain `grep`, `sed -n '1p'`, `cut`, `awk` **without** `exit`.
- Or capture first: `out=$(cmd 2>&1 || true)` then test the variable (`test -n "$out" && echo "$out" || echo fallback`).
- Remember the same rule inside a *detect* string stored in a params/manifest file: it is executed with
  pipefail too, so the trap survives every regeneration unless the string itself is fixed.

## 3. A `{placeholder}` template swallows shell brace expansions

When a skill/params file is rendered by a template engine, `${x#prefix}` and `${x:+word}` are read as
placeholders and the generator aborts with `KeyError: 'unresolved placeholder …'`.

- Use `$x`, a pipe, or `test -n "$x" && … || …` instead of `${…}` forms.
- The same rule applies to any `${…}` a workflow or params file carries: if the renderer only knows
  `{name}` placeholders, braces are not yours.

## 4. A cold-start cost belongs in a warm-up, not in a widened timeout

An installed CLI's first invocations on a cold runner (venv import, container-context probe, first
registry read) can take tens of seconds; the first N cases of a matrix test then time out while the rest
answer in ~0.2 s. Widening the per-case budget hides the thing that budget protects (a wrong invocation
falling through to a download must fail fast).

- Pay the cost once, outside the timed cases: a session-scoped fixture runs one complete, cheap real
  invocation with a generous bound and asserts nothing about its output.
- Keep the per-case timeout tight; a genuine hang still fails loudly in the warm-up.

## 5. Prove a leg's recipe by running its real text

Extract the target's recipe lines from the Makefile, strip the leading tab and make's `@` silencer, then
substitute what make would (`$(VAR)` → value, `$$` → `$`) and run it with `bash -e -c` against a stub whose
helper exits each code you care about. Re-typing the recipe tests your memory of it, not the file.

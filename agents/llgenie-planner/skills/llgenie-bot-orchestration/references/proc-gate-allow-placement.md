# `make check-proc-gate` — `# proc-allow:` marker placement

`scripts/check_proc_gate`-style gates (`make check-proc-gate`) require the
`# proc-allow: <reason>` marker on the **call-site line itself** — the line with
`subprocess.run(` — not on a continuation line of the call.

Wrong (reds the gate — reads a bare, unannotated call site):

```python
shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root,
                       capture_output=True, text=True)  # proc-allow: ...
```

Right (marker on the `subprocess.run(` line):

```python
shown = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=root,  # proc-allow: ...
                       capture_output=True, text=True)
```

## Why it hides, and the fix

`make ci-unit` / `make test` stop at the **first** failing gate, so a proc-allow
placement defect behind an earlier (unrelated) red stays masked until that earlier
red is fixed — then it surfaces as a "new" own-diff failure on the same PR. When a
reviewer reports a proc-gate red that the author never saw, check for a continuation-
line marker before hunting anything exotic.

The fix is one line: move the `# proc-allow:` comment up onto the `subprocess.run(`
line. No logic change, no new vehicle — push to the existing branch.

The CLI is `scripts/check_proc_gate` — it walks the tree for tracked subprocess
call sites and reads each call site line; a call spanning lines must carry its
marker on the first line.

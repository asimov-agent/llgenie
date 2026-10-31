# make profile-drift now runs the live-longer comparison it promised

Issue #1087. The defect was a caller-vs-script contract: `make profile-drift` (Makefile:437) passed
`--only live-longer` to a script whose `argparse` accepted no such flag, so it exited 2 on **every**
invocation — and 2 is also the gate's "could not compare" code, so a broken invocation was
indistinguishable from an unreadable tree. The documented #928 comparison never ran once.

## What was measured

```
$ python3 scripts/check_agent_profiles.py check --only live-longer; echo "exit=$?"
check_agent_profiles.py: error: unrecognized arguments: --only live-longer
exit=2
```

The script has `check` and `report` as its only modes, and finds the host-only `live-longer`
(`prefix-of-the-rulebook`) class only via the full `findings()` walk.

## What changed

`make profile-drift` keeps calling the gate, and the gate now understands the filter:

1. **`--only <key>`** on `check`: a comma-separated list of finding keys; only those classes are
   counted and printed. An unknown key is a broken invocation — exit 2, naming the known keys — never
   a silent "nothing matched" or a green.
2. **Exit codes stay distinct**: a genuine comparison that finds no `live-longer` drift exits 0; one
   that finds drift exits 1; a malformed (`--only bogus`) invocation exits 2 and says exactly that.
   Exit 2 is no longer reused for "never compared".

## Verified, both directions

```
$ make profile-drift                       # before: argparse error, exit 2
$ python3 scripts/check_agent_profiles.py check --only live-longer ; echo "exit=$?"   # after: 0 or 1
```

On this host the tree genuinely carries sixteen `live-longer` truncated-seed files, so the scoped
check exits 1 and names only `live-longer` — never the `absent-from-tree` reverse class a lane is
working down (that is the #928 caller's whole point). A byte-identical tree exits 0. Unit tests drive
`--only` through the real `main()`: scoped-green, scoped-red (another class present is filtered out),
and the unknown-key exit 2.

## Why it matters beyond this target

A control whose documented entry point exits 2 on every run is a control that does not exist — the
same class as #1134 (a gate that printed no FAIL read as clean). A filter flag is how a host-only gate
reports the one class it owns without failing on classes another lane is working down.

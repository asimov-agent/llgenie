# The one-import-root ratchet (ci-unit's post-pytest gate)

## pytest green is NOT the job green
`ci-unit` runs the pytest suite and then a chain of SEPARATE gate steps in the SAME job (`make
check-import-roots`, lint, docs, wiring, …). A job that reds at the very end right after
`2985 passed, 0 skipped` is a **gate step**, not a failing test. Read the job LOG TAIL for the failing
`make` target and its `file:line` — never stop at the pytest summary line and call it green.
```
[import-roots] bare: a NEW import root is refused … (55 now, 54 recorded)
  tests/<new_test>.py:24
make[1]: *** [Makefile:403: check-import-roots] Error 1
make: *** [Makefile:1811: ci-unit] Error 2
```

## A new test file must import through the ONE root
A test file that carries its own bootstrap reds `scripts/check_import_roots.py ratchet`. It refuses two
shapes, both MODULE-LEVEL:
- `sys-path` — a module-level `sys.path.insert(...)` / `sys.path.append(...)` outside `tests/conftest.py`
- `bare` — a top-level `import <scripts module>` / `from <scripts module> import …` (any name that is a
  `scripts/*.py` stem)

`tests/conftest.py` already puts the repo root and `scripts/` on `sys.path` once for the whole suite, so
a new test imports the script as a PACKAGE:
```python
import scripts.ci_frozen_reaper as fr   # resolves via tests/conftest.py — no sys.path.insert, no bare import
```
not
```python
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))   # new sys-path root -> refused
import ci_frozen_reaper as fr               # bare scripts-module import -> refused
```
An `sys.path.insert` inside a test BODY is a different animal and is allowed: it points at a temp tree
the test just built. Only the module-level bootstrap is the seam the rule is about.

## The baseline is SET-shaped; one new site is the red
`tests/fixtures/import-roots-baseline.json` records each rule's counted `file:line` sites, and the ratchet
diffs SETS — a red names the ONE new `file:line` (present now, absent at baseline), never every site the
rule counted. The count may FALL (fixes) and may never RISE. Re-recording with
`python3 scripts/check_import_roots.py --update` just to go green hides a real new root; convert the
import instead. Re-record only when the tree's baseline genuinely moved under you (other lanes added
sites on `main`) — record what the branch actually produces, never a copied old cut.

## Prove the fix with the gate itself, before pushing
Run the same ratchet against the fixed worktree in the test container (the guard walks the tree, it does
not import, so the container's `PYTHONPATH` is irrelevant):
```
python3 scripts/check_import_roots.py ratchet   # exit 0, counts at/below baseline {sys-path: N, bare: M}
python -m pytest tests/<file>.py -q             # the new tests still pass
```
The ratchet exits 0 only AFTER the offending site is gone — that is the proof the gate catches the bug
and now sees its absence. Running it ONLY on the fixed tree demonstrates nothing; confirm the site it
named at `file:line` is the one that disappeared.

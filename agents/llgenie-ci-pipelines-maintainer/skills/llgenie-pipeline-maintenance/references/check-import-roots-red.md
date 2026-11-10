# check-import-roots red: a new import root is a real defect, never a rebase

`make check-import-roots` (issue #796; set-shaped ratchet since #1101) reds the ONE new `file:line`:

```
[import-roots] bare: a NEW import root is refused — this exactly (issue #1101):  (N now, M recorded)
  tests/<file>.py:<line>
[import-roots] sys-path: same  (N now, M recorded)
  tests/<file>.py:<line>
```

## Two forbidden shapes (both refuse a NEW file's own root)

- `bare`: a module-level `import <scriptmodule>` / `from <scriptmodule> import …` where `scriptmodule`
  is a `scripts/*.py` module name, imported bare instead of as `scripts.<module>`.
- `sys-path`: a module-level `sys.path.insert/append(...)` outside `tests/conftest.py` (the one
  allowed seam, which already puts `scripts/` on `sys.path`).

## Why it is a real defect, never a stale-rebase

- The ratchet baseline (`tests/fixtures/import-roots-baseline.json`) is set-shaped and identical on
  `main` and the branch head (a rebase that picks up a newer baseline only matters if `main` itself
  ratcheted; normally it has not). A red that says `N now, M recorded` means the branch added a root
  on top of main's baseline — it survives a rebase unchanged.
- **Never ratchet the baseline up** (`check_import_roots.py --update`): the gate's own doc says a
  baseline "may fall, never rise", and a red `bare: 56 now, 55 recorded` where the +1 is your own new
  file is exactly the target. Ratcheting turns a live gate into a record.

## Remedy (canonical form)

Replace the offender's `sys.path.insert(...)` + bare import with the suite's one-root form
`conftest.py` already enables:

```python
# bad
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import bots_restore_health as b  # noqa: E402

# good
from scripts import bots_restore_health as b
```

## Prove it, then push

```
python3 scripts/check_import_roots.py ratchet   # rc=0: "counts at or below the recorded baseline {sys-path: M, bare: N}"
<venv>/bin/python -m pytest tests/<file>.py -q     # the converted file still passes
```

Then `git add` the file, commit, and (after confirming the fork head is unchanged and the prior run
at the head has concluded) push `--force-with-lease` to the PR branch, and report the new head sha +
the run id where `linux / unit` (which runs `make ci-unit` → `check-import-roots`) is green.

## Classic trigger

A new feature's test that boots `scripts/` itself — the `#1879`/`#1904` case (test file `import
bots_restore_health` bare) reddened both counts 55→56 / 35→36; converting to `from scripts import
bots_restore_health as b` dropped both back and `check-import-roots` re-greened. A lane test author
copying an old bootstrapped test file is the usual source, so for a branch that adds a test,
grep the new file for `sys.path` and `import <scripts-module>` before pushing.

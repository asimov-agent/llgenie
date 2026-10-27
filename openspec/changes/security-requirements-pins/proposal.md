# security-requirements-pins — proposal

Issue: [#754](https://github.com/asimov-agent/llgenie/issues/754)

## Why

The daily security scan is red on its own schedule. Run
[40537601445](https://github.com/asimov-agent/llgenie/actions/runs/40537601445) (`security-scan`,
event `schedule`) exits 1 in `make security-verdict EVENT=schedule` with **8 findings at
critical/high, each with a fix available**, and every one of them is on a pin that lives in the
generated `tools/requirements.txt`:

```
trivy: GHSA-6q48-6c7w-9gw2  certifi 2026.7.22 -> 2026.10.18 (critical)   x2
trivy: CVE-2026-112940      filelock 3.32.5  -> 4.2.1    (high)        x2
trivy: CVE-2026-97687       urllib3 2.7.0    -> 2.8.0    (high)        x2
trivy: CVE-2026-97689       urllib3 2.7.0    -> 2.8.0    (high)        x2
```

Nothing in the repository can move them:

- `tools/requirements.in` names `numpy` and `huggingface_hub[cli]>=0.30` with **no version at all**,
  so the versions that actually run are whatever the resolver picked that minute;
- `certifi`, `filelock` and `urllib3` reach the compiled file only as **transitive** pins, and the
  remediation bot (#717) only edits a *direct* pin in `tools/requirements*.in`.

So each scan re-reports the same three advisories, and a genuinely new one is indistinguishable
from them.

## What Changes

- **`tools/requirements.in` states what the repository intends to run.** The direct runtime
  dependencies are pinned exactly (`numpy==2.4.6`, `huggingface_hub[cli]==1.30.0` — the versions
  the resolver already produced), and the three packages the scan reports carry the **minimum fixed
  version the report itself names** (`certifi>=2026.10.18`, `filelock>=4.2.1`, `urllib3>=2.8.0`),
  each with a comment naming the advisory that demands it. No version is invented: every floor is
  the report's own `fixed` value.
- **`tools/requirements-dev.in` carries the same three floors**, because the test image installs
  the runtime and dev pins together and the dev compile re-resolves the same transitive packages.
- **Both compiled files are regenerated** through the one generator
  (`make -C tools generate-requirements`, `make -C tools generate-requirements-dev`). No `.txt` is
  hand-edited.
- **`tests/test_requirements_pins.py`** locks the shape: every direct runtime pin is exact, every
  scanned package carries an annotated floor, and no compiled pin sits below its floor in either
  compiled file.

Out of scope: `tools/security-floors.in` (written only by `make security-bumps`, never by hand) and
the remediation bot's own placement rules (#739).

## Impact

- The next daily scan's verdict has no blocking finding from these three packages, so a red scan
  means something new.
- `make venv-install` and the test image compile the trust store, the lock library and the HTTP
  transport at their fixed versions.
- A dependency version change becomes a reviewed diff on `requirements.in` instead of a resolver
  side effect.

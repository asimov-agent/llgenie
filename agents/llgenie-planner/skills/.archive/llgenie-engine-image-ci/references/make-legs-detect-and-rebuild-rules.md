# Rules that cost a session: make legs, `detect`, forced rebuilds, probes

Read this before touching llgenie engine CI, bot legs, or a red engine-bump PR. Each rule is
imperative because ignoring it produces a green-looking failure.

## 1. A bot leg's command must not contain a literal comma

`$(call scrubbed_run,…)` splits its arguments on commas in the UNEXPANDED text, so `-s a,b` keeps
only `-s a`. The rest of the command — including its closing quote — is dropped, the shell exits 2
with `unexpected EOF while looking for matching '`, and the leg reports "agent failed" for a reason
that has nothing to do with its task.

- Fix: put the comma-bearing value in a make variable (`LEG_SKILLS := a,b`, use `$(LEG_SKILLS)` in
  the call). The other legs are safe because their comma lives in a separate `_<leg>` target the
  container runs (`bash -lc 'make _issue-refiner'`).
- Prove it, on the EXPANDED recipe:

```bash
make -n <target> | tail -1 | tr -cd "'" | wc -c                  # even = balanced
make -n <target> | tail -1 | grep -o '\-s [a-z0-9,-]*'          # the full skill list
```

- A guard that parses legs must expand simple `NAME := value` / `NAME = value` assignments, or it
  reads `$(LEG_SKILLS)` as a skill name and fails the leg it just got fixed.
- Sweep every leg, not the one that broke: derive the targets from the Makefile (each recipe calling
  `$(call scrubbed_run,…)`) and assert on each expanded line. Run the new test against the pre-fix
  file once — it must fail there, or it describes the defect instead of detecting it.

## 2. No `detect` may pipe into an early-exiting reader

Steps run under `set -o pipefail`. `grep -q`, `grep -m`, `| head` stop reading, the writer takes
SIGPIPE, the pipeline reports 141, and a perfectly healthy binary is reported
`missing (detect exited 141)` while its flag probe passed a second earlier.

- Prefer `{binary} --version` (no pipe at all).
- Otherwise use readers that consume to EOF: plain `grep`, `sed -n '1p'`, `cut`.
- A shell `case`/parameter-expansion detect is fine, but avoid `${…}` — the params generator reads
  `{…}` as a placeholder and dies with `KeyError: 'unresolved placeholder'`.

## 3. A `detect` must execute the binary, never echo the pin

An engine's banner can lag its own tag (pin at a newer version, binary prints an older one). Report
what the binary says; the pin lives in the skill's `version:` and in the image tag. A `detect` that
just echoes `{version}` proves the pin, not that anything is installed.

## 4. Check the built image before declaring a flag missing

An engine that had no `--version` can gain one at a newer pin. Look before choosing a policy:

```bash
docker run --rm <image:tag> bash -lc '<binary> --version; echo rc=$?; <binary> --help 2>&1 | head -3'
```

| what the binary does | `binary_probe` | version comes from |
|---|---|---|
| answers `--version` (usually `--help` too) | `flags` (default) | the probe |
| prints a banner naming itself, no version flag | `help` | the image's `detect` |
| needs its GPU/device to even start the CLI | `device` | the image's `detect` |
| has a banner AND a `--version` | `flags`, and document both flags | the binary |

After a skill change: `make generate-engine-params ENGINE=<id>` → `make check-engine-params`
(0 stale) → `make build-engine` + `make test-engine-image`. The tag hash changes with the params, so
that build really is a rebuild.

## 5. `--force` alone is not a rebuild

If the build still passes `--cache-from`, a "forced" build is a cache hit that re-tags the previous
layers. A real forced build adds `--no-cache`, drops `--cache-from`, and passes `force` down to the
shared base builder as well. Verify:

```bash
make build-engine ENGINE=<id> ARCH=<arch> FORCE=1 2>&1 | grep -E "no-cache|cache-from|built "
```

Expect `--no-cache` on the base build AND the engine build, and no `--cache-from` anywhere. Sweep
form: `make build-engines FORCE=1 VERIFY=1 JOBS=<n>` — every row must end with `OK image test`.

## 6. A publish carries three names

The immutable `<sha8>-<hash>-<variant>` tag, the moving `:<arch>` tag, and `:latest` — claimed by
exactly one variant per engine (cpu first, else its only/first variant) so parallel publishing rows
cannot race that tag. Treat a not-yet-published `:latest` as a note, never a failed pull, or every
unchanged engine reddens the published-image stage right after the tag is introduced.

## 7. Reading CI failures

```bash
gh api repos/<owner>/<repo>/actions/runs/<run>/jobs --paginate | python3 -c '…'   # job ids
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences
```

- `--allow-escape-sequences` is required or `gh` refuses the log with "the response contains terminal
  escape sequences".
- `gh pr checks <n>` shows the failing job URL; the trailing number is the job id.
- Same test failing on the PR branch AND on a clean main worktree = environment/network, not the PR.
  Compare before you fix anything.

## 8. Installed-launcher tests and cold starts

The first few invocations of the installed `~/bin/llgenie` can each exceed a 30 s per-case budget on
a cold runner (venv import, docker-context probe), then answer in ~0.2 s. Do NOT widen the per-case
budget — it exists so a launcher that falls through to a download fails fast. Pay the cold start once
in a session fixture with a wide bound, asserting nothing about the output:

```python
WARMUP_TIMEOUT = 180

@pytest.fixture(scope="session", autouse=True)
def _warm(...):
    subprocess.run([str(launcher), "--matrix", "--arch", "cpu", "--vram", "8", "--ram", "64"],
                   capture_output=True, text=True, timeout=WARMUP_TIMEOUT, env=env, input="")
```

## 9. Why an engine-bump PR is red

- Hours-old red is usually **stale**, not wrong: `DIRTY` = conflicts, `BLOCKED` = a failing required
  check. Check whether the rebase leg actually ran — its log names the cause (an unclosed quote from
  §1 looks like an agent failure).
- Rebase onto `origin/main` yourself before judging the content; the branch inherits every fix main
  gained while it waited, and often that alone clears the red.
- A data-shape test that asserts "at the current pin every X is hosted/Y" pins a SNAPSHOT. Correct
  bumps surface the documented exception, so such a test must state the invariant and assert the
  product's refusal path for the excepted case.
- Verify the bumped image at the new pin, and read the version it prints.

## 10. Remotes in this checkout

`origin` = upstream `asimov-agent/llgenie`; `fork` = `andyholst/llgenie`. Push feature branches to
`fork` and open the PR with `--head andyholst:<branch>` (base repo `asimov-agent/llgenie`, base
`main`). A push to `origin` leaves a stray branch on upstream and the PR create fails with
"No commits between … and …".

# Make and shell failure modes that cost hours in this pipeline

Every recipe here runs through GNU make, then `bash -euo pipefail` inside the engine image or the
agent image. Four failure modes recur, each with a cheap proof.

## `$(call …)` truncates its argument at a literal comma

GNU make splits the arguments of `$(call macro,arg…)` on commas in the **unexpanded** text, then
expands. A literal comma inside the argument — `-s skill-a,skill-b`, a JSON array, a version pair —
silently drops everything after it.

Symptom when the argument is a `bash -lc '…'` command:

```
/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `''
```

the step exits 2 and the tool inside never runs. It reads like a quoting bug in the tool; it is the
macro eating the tail of the command.

Rules:

- **Never put a literal comma in a `$(call)` argument.** Move the comma-bearing value into a variable
  (`LEG_SKILLS := skill-a,skill-b`) and reference `$(LEG_SKILLS)`. The call text then contains no
  comma and the expansion restores it.
- **Proof:** `make -n <target> | tail -1` — the expanded command must have an *even* number of single
  quotes and must still contain the whole argument list. A target whose command is short by half is
  the defect, and `make -n` shows it without running anything.
- **A guard that reads recipe text must expand the Makefile's own assignments first** (`NAME := value`,
  `NAME = value`, top-level lines only). Otherwise it reads `$(LEG_SKILLS)` as a literal value, reports
  a phantom "unknown skill"/"missing file", and the fix looks wrong.

## `set -o pipefail` + an early-exiting reader = exit 141

With `pipefail` the pipeline's status is the first non-zero one. A reader that stops at the first
match — `grep -q`, `grep -m1`, `head -1`, `awk … exit` — closes the pipe; the writer takes SIGPIPE
(141) and the whole step fails even though the command it wraps succeeded.

Symptom: a perfectly good binary reported `missing (detect exited 141)`, or a step failing with no
error text of its own.

Rules:

- **Readers must run to EOF:** plain `grep` (no `-q`/`-m`), `sed -n '1p'`, `cut`, `sort`.
- **Never pipe an engine's own output into `head`** in a `detect`/`install` step.
- **Guard:** assert no step matches `grep -q`, `grep -m`, `| head`. That guard catches the shape for
  every engine at once, including ones nobody has hit yet.

## A version must be a version

A version probe may print the engine's own self-report, or the pinned version when the distribution
reports nothing usable (`0.0.0`, empty). **Never the commit sha** — it has no dots, so any "is this a
version" check rightly rejects it, and the stage reds on a healthy engine.

- Prefer the binary's own `--version`; if the CLI has none, take the help family and read the version
  from the package metadata, falling back to the pin.
- **Run the built image's binary with each candidate flag before declaring a probe policy** — a CLI can
  gain `--version` at a new pin, which turns a "no version flag" assumption into an unnecessary
  exemption:

  ```bash
  docker run --rm <image> bash -lc '<binary> --version; echo rc=$?'
  docker run --rm <image> bash -lc '<binary> --help | head -6'
  ```

- Do not parse a usage/banner block for a version by position: the first line naming the program is
  usually `prog <subcommand> …`, not `prog <version>`. Match a version-shaped token or use the CLI's
  own flag.

## Force must mean force

A `--force` that only skips the "image already available" check still reads the registry layer cache
(`--cache-from`), so a fully cached build re-tags the previous layers and compiles nothing. A forced
rebuild must therefore:

- pass `--no-cache` and read no `--cache-from`;
- propagate `force` to the base/toolchain image builder, not just the engine image;
- be forwarded by the parallel fan-out target, or a whole-matrix forced sweep is impossible.

**Verify from the log, not the flag name:** the buildx argv is echoed (`$ docker buildx build …`), and
a real recompile shows hundreds of compiler lines. A "forced" build with three log lines did nothing.

## Publish names and who owns `:latest`

Publish each image under three names — the immutable hash tag, the moving per-arch tag, and `:latest`.

- `:latest` must be claimed by **exactly one variant per engine** (the cpu variant when the engine has
  one, else its only variant). Rows publish in parallel; two variants writing `:latest` means the last
  writer wins, non-deterministically.
- On rollout of a new tag name, treat **absent** as a note and **present with a different digest** as a
  failure. Otherwise every engine that does not happen to be rebuilt in that run reds the
  published-image stage.

## Verify a publish without trusting the log

```bash
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences \
  | grep -E 'engine-image\] pushed'

docker manifest inspect <registry>/<name>:latest \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["config"]["digest"])'
```

Compare the config digests of `:<arch>` and `:latest` against the hash tag: equal digests prove the
moving tags point at the same image, which the job log alone cannot show.

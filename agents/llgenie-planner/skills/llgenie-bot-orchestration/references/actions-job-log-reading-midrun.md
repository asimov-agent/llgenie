# Reading a failing job's real error from GitHub Actions — including mid-run

**Trigger:** a lane reports "CI can't show the error" (BuildKit `\r` collapse, blank gap between buildx line and FAIL), or a run is `in_progress` but a specific cell already concluded FAILURE and the real failing layer is needed now rather than after the whole run settles.

## `gh run view --log-failed` does NOT work while the run is in_progress

```
$ gh run view <RUN> --log-failed
run <RUN> is still in progress; logs will be available when it is complete   (rc=1)
```

So mid-run, `--log-failed` is useless even when individual jobs have concluded.

## Job-level log endpoint works mid-run and redirects to a presigned blob

Get the failing job IDs from the run:

```bash
gh api "repos/asimov-agent/llgenie/actions/runs/<RUN>/jobs" \
  --jq '[.jobs[]|{id,name:.name,status,conclusion}]'
```

A job's full log (every step, incl. the docker/BuildKit `=> ERROR` lines) is:

```bash
curl -sL -H "Authorization: Bearer $(gh auth token)" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/asimov-agent/llgenie/actions/jobs/<JOBID>/logs" \
  -o /tmp/joblog-<JOBID>.txt -w "http=%{http_code} bytes=%{size_download}\n"
```

- **Without `-L` the API returns HTTP 302** (to `productionresultssa*.blob.core.windows.net/...`) — follow redirects or you read 0 bytes.
- Prefer `curl -L` over python `urllib`: urllib may return HTTP 401 even with `Authorization: Bearer` for this endpoint and does not transparently re-send auth to the blob host (correct — the secret is the signed URL, not the token).
- The log is `\r`-line-delimited in places; if grepping for `=> ERROR` you may need `tr -d '\r' < file | grep -aE "=> ERROR|ERROR: failed to solve|exit code [12]"` first.

## Interpreting the real failure (docker buildx)

`--progress=plain` makes BuildKit emit per-layer lines (e.g. `#9 498.2 ...`). Find:

```
#9 481.9 Copying rust artifact from rust/target/release/vllm-rs to vllm/vllm-rs   <— earlier layers SUCCEEDED
#9 481.9 warning: Failed to parse pyproject.toml ...
... No "FindHIP.cmake" found in CMAKE_MODULE_PATH ...
subprocess.CalledProcessError: Command '['cmake', ...    <— setuptools_rust → cmake step FAILS
#9 ERROR: process "/bin/sh -c chmod +x entrypoint.sh && python3 engine_runner.py install params.json && rm -rf /root/.cache" did not complete successfully: exit code: 1
ERROR: failed to solve: failed to build: ... exit code: 1
```

- `#N <sec>.ms` is BuildKit timing (time into that layer).
- A `warning: Failed to parse pyproject.toml — unknown field` can be a real cause even though it says "warning" (breaks settings discovery → wrong build path).
- Quote the `#N ERROR:` line + the first `subprocess.CalledProcessError` frame — that's the actionable fact.
- `exit code 143` = SIGTERM (job killed, e.g. timeout), a *different class* from a build failure — say "did not complete", don't fold it into the docker-layer diagnosis.

## Discipline

- Carry the run id AND job id AND head sha in every quoted finding — a failure without a run/job id is a claim about time, not the branch.
- Don't wait for the whole run to settle before reading a concluded cell's log — but say exactly what you grounded (job id + run id + the quote), never "CI can't show it" once the endpoint works.
- A tooling change that adds `--progress=plain` is not a hashed image input (no tag shifts) — it only makes the real error visible; verify the image-input set (`scripts/engine_skills.py::_image_inputs`) before claiming tag effects.

## A fold that drops the trailing newline breaks byte-identity AND reds lint

A live→tree profile fold ("byte-identical") can silently lose the file's final newline. Measured on #1447: the submitted `dead-workflow-and-trigger-proof.md` was md5 `222606522e…` (no trailing `\n`, `od -c` shows `\ No newline at end of file`), while the live source was `cec492a9…` ending `\n`. The result is two independent reds that look unrelated: `linux / lint` fails (`LINT FAIL — files missing a trailing newline`) AND `scripts/check_agent_profiles.py` reports the file as present-but-different (byte-identity broken).

So when a fold's lint/scope job reds on a reference file, do not trust the lane's claimed tree==live hash — **diff the live file against the committed blob**:

```bash
git cat-file blob <head>:agents/<lane>/skills/<skill>/references/<file>.md | md5sum   # committed
md5sum <live profile path>                                                            # live source
git cat-file blob <head>:…/<file>.md | tail -c 20 | od -c                            # final byte: \n or missing
```

The correct fix is **regenerate the committed copy verbatim from the live source** (`cp`, never a partial re-write) so the committed md5 equals live (newline included). Ten "stay byte-identical to md5 X" instructions are wrong when X is the *broken* no-newline hash. Update the issue/PR's stated md5 anchor to the byte-correct live hash at the same time, so the acceptance criterion does not bless the broken copy. (owner-verified 2026-11-01)

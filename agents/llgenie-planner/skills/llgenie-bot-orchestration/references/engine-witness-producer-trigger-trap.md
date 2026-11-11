# Engine-build witness: producer run vs pr-trigger run (binding verdict trap)

WHEN: binding a vllm-rocm (or any cell) build verdict to an issue acceptance criterion.

TRAP: two live runs at the SAME head look like two witnesses. They are not equal.
- `engine-build-pr-trigger` (event=pull_request): its only meaningful job is `trigger` — it WAITS on the producer and carries NO matrix cell. Reading its job conclusion is a trigger, not a build verdict.
- `engine-build` (event=workflow_dispatch): the producer that actually runs the matrix cells — `engine-build-vllm-rocm`, `-cuda`, `-cpu` (job names start with `engine-build-vllm-`).

RULE: the verdict line for a cell criterion must name the PRODUCER run id + the CELL job id + head_sha, e.g. `run=42159549121 job=127701755286 head=ea0b9033a9`. Never the pr-trigger run (`42155990380`/`127701586884` in this case).

VERIFY: fetch `actions/runs/<id>/jobs` and select the job whose name is the specific cell (`engine-build-vllm-rocm`), not `trigger`/`guard`/`matrix`. The run that hosts that job is the binding producer.

LESSON (llgenie 2026-11-06): both a lane DM and the wire binding record must cite the same run+job; posting from the pr-trigger's conclusion was the risk. On-issue record 6676789063 on #1696 binds it.

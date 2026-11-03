# OpenSpec image drops to a non-root default user (issue #1646)

`openspec/Dockerfile` left its default `CMD` running as `root` (the image had no `USER`
directive), which the daily semgrep scan reported as a `high` `dockerfile.security.missing-user`
finding at line 30. Semgrep's `missing-user` rule requires a non-root `USER` before the
container's `CMD`/`ENTRYPOINT`, and no package pin can clear a `component:code` finding — the fix
is in the file.

The image now declares `USER 65532:65532` immediately before the `CMD`. This is the same
least-privilege convention the scanner images already use (`containers/scanners/semgrep/Dockerfile`).
It does not change the Makefile's real invocation: `OS_OPTS` still runs the container with
`-u root` (the `openspec new/validate/status/shell` targets write into the bind-mounted repo at
`/repo`), so the CLI's write paths are unaffected — only the bare image's default (the `--help`
drop-in) now runs as an unprivileged user.

Verified against the real `p/default` semgrep pack (`containers/scanners/semgrep/Dockerfile`,
ref `ghcr.io/asimov-agent/llgenie/semgrep:69170b46efd8`), not assumed: the unmodified file reports
`dockerfile.security.missing-user.missing-user` at `openspec/Dockerfile:30`; the fixed file reports
0 findings for the rule on that path. A non-root `docker build` + `docker run` of the fixed image
confirms `openspec --help` exits 0 as `USER 65532`.

#1646

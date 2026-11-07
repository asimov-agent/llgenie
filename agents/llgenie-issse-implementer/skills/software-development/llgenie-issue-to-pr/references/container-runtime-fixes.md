# Making a container image run as non-root

The heavy `llgenie/agent` image installs its toolchain (hermes, skills, `.local/bin`
launchers) at build time, then had no `USER` — so it ran as root. The fix is a
`USER agent` runtime user, but the install chain is the hard part.

## Install into the non-root home from the START; never copy-then-relocate

The tempting fix — keep `HOME=/root`, finish the install as root, then `cp -a /root/.hermes
/home/agent/.hermes` and `USER agent` — FAILS. The installed tree embeds the old absolute
path in hundreds of places: the venv `bin/python` shebangs, the `~/.local/bin/hermes`
launcher shims, `pyvenv.cfg`, console-script entry points. A copy leaves every one of them
pointing at `/root/...`, which the non-root user cannot read → `Permission denied` the moment
CMD runs `hermes --version`. Rewriting them after the copy is whack-a-mole across ~700 files.

The correct shape:

```dockerfile
# after the user exists, BEFORE the install RUN lines that write $HOME / $HERMES_HOME
RUN useradd -r -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent \
    HERMES_HOME=/home/agent/.hermes \
    PATH="/home/agent/.local/bin:${PATH}"
# ... install chain runs here, writing straight into /home/agent ...
RUN chown -R agent:agent /home/agent   # only if something ran as root after
WORKDIR /repo
USER agent
CMD ["bash","-lc","git --version && gh --version && hermes --version && hermes plugins list | grep -q nerve"]
```

Because `HOME`/`HERMES_HOME`/`PATH` point at the non-root home BEFORE the installers run,
every shebang and launcher is written with the correct path — no relocation, no rewrite.
Keep a `USER root` at the top only where apt/install genuinely needs it; the LAST `USER`
before `CMD` is the runtime identity, and it must be non-root.

Set only ONE `ENV HERMES_HOME` / one `ENV PATH` — a leftover duplicate `ENV HERMES_HOME=/root/.hermes`
later in the file silently re-points the runtime back at root.

## Verify by actually building and running the CMD

The semgrep rule (`dockerfile.security.last-user-is-root`) only checks the LAST `USER`; it
clearing is necessary, not sufficient. Build the flattened context the publish workflow uses
(agent `FROM ${TEST_IMAGE}`, context = the Dockerfile + every script it COPYs), then run the
image's own CMD and assert it is non-root and works:

```bash
docker run --rm --entrypoint id <built-tag>              # uid must not be 0
docker run --rm <built-tag>                              # the image CMD exits 0, hermes runs
```

A green default CMD plus `uid != 0` plus `hermes --version` reporting the relocated
`Install directory: /home/agent/.hermes/...` is the acceptance. Run the container test
baseline too (`make test` — the hermetic fast group + install host) so the base image is
still sane.

## Whether a Dockerfile change owes the docs trio depends on the path CLASS

Neither automatically doc-exempt nor automatically doc-owing — check the path against
`NOTE_SURFACE_RES` in `scripts/check_docs.py`. Some image directories are NOTE_SURFACEs (and
owe the `agent-wiki` note + `changes.d` fragment + regenerated `CHANGES.md`); others are not
and owe nothing. `make check-docs` at the committed head is the only authority; run it early
and it names the exact path it wants a note for.

For the semgrep side (missing-user, and which uid may write a bind mount) see
`references/security-scan-findings.md`.

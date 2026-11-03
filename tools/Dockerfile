# GGUF tooling: pip-compile resolver container (matches repo pattern).
# Build with nerdctl, run to compile requirements.in -> requirements.txt.
FROM python:3.11-slim

RUN pip install --no-cache-dir pip-tools

# The tool runs WITHOUT a `-u root` override (tools/Makefile) and pip-compile
# writes requirements.txt back into the host dir bind-mounted at /work (owned by
# the invoking user). A non-root container user must therefore match the host
# uid so the write succeeds; 1000 is the standard first-user uid this tool runs
# under. This also satisfies semgrep's dockerfile.security.missing-user rule,
# which flags a container whose CMD runs as root (issue #1647).
RUN useradd -u 1000 -m tooluser

WORKDIR /work
USER tooluser

# The requirements.in is bind-mounted at /work by the Makefile; this container
# only pins CONTAINER-side tooling (pip-tools). Runtime deps are compiled by
# pip-compile against the mounted .in file.
CMD ["pip-compile", "requirements.in", "-o", "requirements.txt"]

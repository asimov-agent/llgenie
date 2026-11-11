# Secrets in a containerized Actions pipeline: forwarding + audit

## Getting every key into the running container AND the agent's shell

A `docker run -e KEY` only puts the secret in the Hermes process env. Inside the
bot image the agent's SPAWNED terminal tool does NOT inherit those plain vars —
`echo "$NOUS_API_KEY"` in the agent's shell returns empty, so the agent cannot
scrape/curl with the credential. The value is fine; it is just invisible to the
agent's shell.

Fix: in the docker entry derive a forced copy of each key under a predictable
prefix and pass BOTH names on the run line:

- docker run line: `-e KEY -e _HERMES_FORCE_KEY` (names only; the value is set
  from `$KEY` inside `DOCKER_RUN`, so the real value never appears in argv / `ps`).
- A `_HERMES_FORCE_KEY` env survives into the agent's shell where the plain
  `KEY` does not.

Which keys need this: every key the AGENT uses in a shell (the Firecrawl scrape,
git-with-token, a model provider). Keys only the Hermes process itself reads need
no forced copy — the agent never calls them.

Test the forwarding INSIDE the real bot/test image (the one carrying Hermes, has
`/.dockerenv`), never on the host and never with an empty env. A host test that
passes an empty env to a child "proves" a pass because nothing was set to leak in
the first place — a false green. The image check must be RED on the old
Dockerfile/Makefile and GREEN on the new one, and the CI job must pass with the
real secrets (assert `container=set agent-shell=set` for every key). The value is
never printed; the check prints only set/unset words.

## Auditing Actions run logs + artifacts for leaked secret values

Procedure:

1. Enumerate runs and download each log: `gh api repos/O/R/actions/runs/<id>/logs
   > runs/<id>.zip`, unzip, scan every line.
2. Artifacts too: `gh api repos/O/R/actions/artifacts` lists them; anyone logged
   into GitHub can download public-repo artifacts, so scan them as well.
3. "Bad zips" from the docker build step are not zips — they are gzip-encoded
   build records. Decode with gzip, not zipfile.
4. Inside a still-unexpired artifact-download URL an `sk-...` is a signed blob
   URL that expires and is not a credential — do not treat it as a leak.
5. Scan for two things:
   - Credential SHAPES regardless of key name: `ghp_`/`gho_`/`ghu_`/`ghs_`/
     `ghr_`/`github_pat_`, `fc-`, `hf_`, `sk-`/`sk_`, `ev_`, `Bearer <tok>`,
     JWTs, `-----BEGIN ... PRIVATE KEY-----`, `user:pass@` URLs. Search both the
     decoded text AND the raw bytes of decoded gzip files.
   - KEY-only assignments `KEY=<value>` for each secret name. Classify every
     match: `***` (masked), `<placeholder>`, `container=set`/`agent-shell=set`
     status words, `${{ ... }}` comptime and `...` are SAFE — a short value is
     NOT proof of a leak.
   - Confirm no step enables `##[debug]` logging.

## The certainty boundary (state it, never over-claim)

A shape+literal scan CANNOT prove a value was never exposed. It rules out:

- every known credential shape, and
- the literal value of any secret that happens to be in YOUR shell (compare raw,
  base64, url-encoded, and both halves).

It cannot rule out: a prefixed-less raw value printed against a name you do not
hold, a value split across lines, history purged before you looked, or run logs
GitHub already deleted (a `404` on the logs endpoint means the run is gone and
unverifiable — say so). Say "no shape matched" and "no value I could search for
was present", never "nothing was exposed". When pressed for a guarantee the
honest answer is this boundary, stated plainly.

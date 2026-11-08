# dirty-watch-detector-gh-path

## Why

The rebase lane's DIRTY watch (cron `244a75ddc597`) crashed every tick with
`FileNotFoundError: [Errno 2] No such file or directory: 'gh'`. `dirty-detector.py` spawned bare
`"gh"`, and a cron process runs with a minimal PATH that omits `~/.local/share/mise/shims`, which is
where `gh` lives on this host. The job auto-paused after the first failure.

A detector that raises is worse than one that reports red: the cron gate suppresses a *quiet* tick by
byte-identical output, so a crashed run reads as silence — and silence is indistinguishable from
`conflicting: none`. Measured while it was dead: five PRs were genuinely `CONFLICTING` on the board.

The script had also never been tracked: `pr-fleet-monitoring.md` documents its output contract by
name, yet `git ls-files | grep dirty-detector` returned nothing, so the fix had no reviewable
artifact and `make sync-agent-profile` (tree to profile) would never restore it.

## How

Resolve both binaries the way a login shell would — `shutil.which(name)`, then an explicit fallback
list (`~/.local/share/mise/shims`, `/usr/local/bin`, `/usr/bin`, `/bin`), then the bare name so a
total failure still names the binary — and version the script into the tree under
`agents/llgenie-pr-merge-conflict/scripts/`.

## Benefits

- The watch measures again under cron's own environment instead of dying before it reads anything.
- The lane's monitor becomes a reviewed, tracked artifact matching the reference that describes it.

## Non-goals

- No change to the quiet-path contract (`conflicting: none` stays byte-identical) or to the conflict
  path's `measured at main <sha>` line.
- Does not touch the unrelated curator drift in `measurement-and-readback.md` (issue #1169).

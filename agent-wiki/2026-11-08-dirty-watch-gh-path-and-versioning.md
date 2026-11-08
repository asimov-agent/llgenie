# The dirty-watch detector must resolve `gh` itself, and live in the tree

`llgenie-dirty-watch` (cron `244a75ddc597`, issue #2125) crashed every tick with
`FileNotFoundError: [Errno 2] No such file or directory: 'gh'`: the detector spawned bare `"gh"`, and
a cron process runs with a minimal PATH that omits `~/.local/share/mise/shims`, which is where `gh`
lives on this host. The job auto-paused after the first failure.

A detector that raises is worse than one that reports red. The cron gate suppresses a *quiet* tick by
byte-identical output, so a crashed run reads as silence — and silence is indistinguishable from
`conflicting: none`. Measured: five PRs sat genuinely `CONFLICTING` while the watch had been dead.

The fix resolves both binaries the way a login shell would — `shutil.which(name)`, then an explicit
fallback list (`~/.local/share/mise/shims`, `/usr/local/bin`, `/usr/bin`, `/bin`), then the bare name
so a total failure still names the binary — and versions the script into the tree at
`agents/llgenie-pr-merge-conflict/scripts/dirty-detector.py`.

The versioning half matters on its own: `pr-fleet-monitoring.md` already documents this script's output
contract by name, but the file had never been tracked. A fix applied only to the live profile has no
reviewable artifact and no durability — `make sync-agent-profile` copies tree→profile, so it would not
restore it, and a profile rebuild would silently drop it.

Proven: `env -i HOME=$HOME PATH=/usr/bin:/bin python3 agents/llgenie-pr-merge-conflict/scripts/dirty-detector.py`
prints `conflicting: …` / `conflicting: none` and exits 0 (the exact failing condition), and
`make sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1` reports the profile matches the tree
byte for byte.

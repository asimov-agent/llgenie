## Tasks

- [x] Replace `subprocess.call` with a polled `Popen` loop in `scripts/unit_tests.py`.
- [x] Emit a timestamped heartbeat at a bounded cadence with an env override for replay.
- [x] Prove the negative control: the new tests fail on the old tree.
- [x] Prove the cadence with a clean 3-second replay (`rc=0`, three heartbeats).
- [x] Assert the 120-minute job ceiling is unchanged.
- [x] Add the note trio and validate the OpenSpec change.

# Tasks — provision-agent-profiles (issue #2165)

- [x] Add `scripts/provision_agent_profiles.py` materialising every lane's agents/<profile>/ into its home, idempotently, reusing agent_profile_sync write/check
- [x] Add `make provision-agent-profiles` and wire it into `make install` (the real setup/rebuild path)
- [x] Add the `--check` post-provision gate that fails naming profile + path on divergence
- [x] Add `tests/test_provision_agent_profiles.py` (temp home: fresh match, red on missing/mutated + green after re-provision, own-files survive, idempotence)
- [x] Open the ready-for-review PR closing #2165

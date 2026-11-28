## Tasks

- [x] Register the checkout skills in every installed lane profile at agent-image build time, with build-time read-back (#3121).
- [x] Fail the issue-bot job when triage fails, no verdict is reached, or `implement` opens no vehicle (#3121).
- [x] Refuse a forced dispatch onto a `blocked` issue as `action=blocked` (#3121).
- [x] Add regression tests covering the blocked target and the triage-leg failure layer (#3121).
- [x] Prove in a forced no-vehicle harness that the guard exits 1 with the triage rc / no-vehicle annotation, while a `refine` verdict or a real PR exits 0 (proven: extracted workflow shell at head `d5858e861` — `TRIAGE_RC=1 rc=1`, `NO_VEHICLE_RC=1`, `REFINE_RC=0`, `VEHICLE_RC=0`).

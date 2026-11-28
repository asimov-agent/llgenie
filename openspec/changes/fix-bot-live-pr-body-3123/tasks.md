## Tasks

- [x] Fetch the live PR body/head/base before fix-loop-image and pass them to the check loop (#3123).
- [x] Fail with `exit=2` and no `fixed` marker when a body-dependent check has an empty body/head/base (#3123).
- [x] Ignore and roster the `fix-bot-pr-body.md` run input (#3123).
- [x] Add workflow-shape regression tests and prove they fail on the old tree (#3123).
- [x] Prove the extracted check-loop guard exits 2 with the empty-body annotation at the fixed tree (#3123).

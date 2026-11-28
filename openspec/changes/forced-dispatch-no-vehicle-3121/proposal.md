# Forced dispatch must not report a no-vehicle success (#3121)

`issue-bot.yml` forced dispatch could end `completed success` after the triage leg died on
`unknown_skill`, leaving no verdict, no branch and no PR. The global Hermes config registered the
checkout's skills, but a lane leg runs under `-p <lane>` and resolves them from its profile config.

## Why

A silent no-op consumes a daily cap slot, posts a claim comment and looks like a successful
hand-off on the board. The state.db session error observed in the same second is only a consequence
of the triage leg never starting.

## What changes

- Register `/repo/.hermes/skills` in every installed lane profile at image build time, with a
  read-back that fails the build when a registration is missing.
- Fail the workflow after the durable outcome comment when the triage leg failed, no verdict was
  reached, or an `implement` verdict produced no changed tree, no pushed branch and no PR.
- Refuse a forced dispatch onto an issue carrying `blocked` as `action=blocked` before claiming it.

## Capabilities

- New capability: `forced-dispatch-no-vehicle`
- Modified requirement: the issue-bot must never report green without a verdict or a vehicle.

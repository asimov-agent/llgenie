# Fixture lane reference — planted QUALIFIED teaching (issue #2502)

This occurrence is qualified on purpose: the line names the amend/integrate ancestor case, so the
hygiene check must leave it green.

Push an amended head with `git push --force-with-lease --force-if-includes origin <branch>` — the
amend keeps the remote tip an ancestor of the new head, the only sanctioned case for the flag.

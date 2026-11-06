# engine-pins evidence-aware skip (agent-wiki note)

The `engine-pins` job in [#1696](https://github.com/asimov-agent/llgenie/pull/1696)'s
ci.yml diff polls for repinned engine images; previously it burned a deterministic
`WAIT=290`-minute timer-fail whenever the pin-producing engine-build cell was red
(issue #1844). It now reads the producing cell's conclusion first and, on a red cell,
records a `SKIPPED` decision (engine, run id, red conclusion) and concludes immediately.
The wait is preserved for green-but-not-yet-published cells, so the gate is not weakened.

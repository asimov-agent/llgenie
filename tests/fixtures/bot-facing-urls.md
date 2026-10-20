# The URLs a bot run is expected to be able to read (issue #380)

`make web-coverage` reads this file when no issue names a URL, and prints one line per URL with its
HTTP status, exiting non-zero when one is dead. It is a fixture rather than a hard-coded list so a
reviewer sees exactly what is being checked, and so adding a dependency is a reviewable edit.

These are the destinations the bots actually depend on:

- the repository they work in — <https://github.com/asimov-agent/llgenie>
- the Hub every model/engine path resolves through — <https://huggingface.co>
- the upstream the engine skills pin against — <https://github.com/ggml-org/llama.cpp>
- the API host the issue tooling talks to — <https://api.github.com>

A URL that returns 401/403 is **not** counted dead: the resource exists and wants a credential the bot
does not have, which is a different problem from a link nobody can read.

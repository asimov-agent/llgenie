# An engine container dies when the test that started it exits (issue #1669)

`~/bin/llgenie-engine-*` and the llama-server shims background `docker run` and only
removed the container when that script itself exited. A test, or the engine-improver
serve steps, start the launcher in the background. A non-interactive shell does not
SIGHUP a background job when it exits, so the container and `llama-server` stayed up
after the test was done. On this host that left `llgenie-llama-cpp-11434` serving a
27B model after an acceptance run whose pytest process was already gone.

The generated scripts now remember their parent pid. When that parent is gone they
exit, and the existing trap runs `docker rm -f` on the container. A parent that is
still alive — an interactive serve — is not touched.

A pytest session records the `llgenie-*` containers already running when it starts
and, when it finishes, removes only the ones that appeared during the session.

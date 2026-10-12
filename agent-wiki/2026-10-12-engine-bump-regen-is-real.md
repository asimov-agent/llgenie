# Engine bump regen is real

Issue #192. The earlier fixture Makefile target was `@true`. The Dockerfile
check called `render_dockerfile` after `bump()` returned. The fixture make
target now calls `write_params`, and the test reads the files it wrote.

The TensorFold v1.0.7 pin only removed pyproject packages. `DEPS` was silent
because it printed only additions. It now prints `python_removed` too.

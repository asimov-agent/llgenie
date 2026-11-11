# Registering a project's skills for headless Hermes

Companion to section 7 of the skill. Everything here was measured against
`hermes-agent==0.19.0` (the version PyPI caps at for Python 3.12) and against a
newer local CLI.

## Why registration is required

Hermes discovers skills from:

1. its own home (`~/.hermes/skills`),
2. `skills.create_dir`,
3. `skills.external_dirs`,
4. a **trusted** project root (project discovery).

`hermes -z "…" -s <name>` resolves against those roots only. A checkout that is
merely bind-mounted into `/repo` is NOT automatically a skill root. Without one
of 2–4 the preload returns no skills and the run proceeds with an empty
contract — while exiting 0.

`skills.external_dirs` is the most portable seam: it exists on every CLI this
repo can install and does not depend on a per-repo trust decision. Prefer it
over `skills.project_discovery` + `skills.trusted_project_dirs`, which newer
CLIs support but the pinned one may not.

## The pinned-CLI trap

```bash
hermes config set skills.external_dirs '["/repo/.hermes/skills"]'
hermes config get skills.external_dirs
# → ["/repo/.hermes/skills"]
```

That looks right, but on `hermes-agent==0.19.0` the value is written to
`config.yaml` as a **quoted string**:

```yaml
skills:
  external_dirs: '["/repo/.hermes/skills"]'
```

and the loader treats it as ONE directory literally named
`["/repo/.hermes/skills"]`, which does not exist. Resolution is zero. Newer
CLIs parse the same argument into a real list. The portable fix is to write the
YAML list yourself:

```yaml
skills:
  external_dirs:
    - /repo/.hermes/skills
```

## Registration script (write YAML, then verify)

```python
#!/usr/bin/env python3
"""Register a directory in skills.external_dirs of a Hermes home."""
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def register(home: Path, directory: Path) -> None:
    config = home / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if config.exists():
        text = config.read_text(encoding="utf-8")
        data = (yaml.safe_load(text) if yaml else {}) or {}
        if not isinstance(data, dict):
            raise SystemExit(f"{config} is not a YAML mapping; refusing to overwrite")
    skills = data.setdefault("skills", {})
    dirs = skills.get("external_dirs")
    if isinstance(dirs, str):          # repair the JSON-literal shape
        dirs = []
    dirs = list(dirs or [])
    if str(directory) not in dirs:
        dirs.append(str(directory))
    skills["external_dirs"] = dirs
    if yaml:
        config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:                              # minimal writer when PyYAML is absent
        config.write_text(
            "skills:\n  external_dirs:\n" + "".join(f"    - {d}\n" for d in dirs),
            encoding="utf-8",
        )


def verify(home: Path, directory: Path) -> bool:
    config = home / "config.yaml"
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    return str(directory) in text and '\"[' not in text


if __name__ == "__main__":
    home, directory = Path(sys.argv[1]), Path(sys.argv[2])
    register(home, directory)
    if not verify(home, directory):
        raise SystemExit(f"registration of {directory} did not land in {home}/config.yaml")
```

Call it from the image's install script (`--home "$HERMES_HOME" --dir
/repo/.hermes/skills --check`) so a build that fails to register fails the
BUILD, not a bot run ninety minutes later.

## Proving the load without spending a model call

`agent.skill_commands.build_preloaded_skills_prompt(skill_identifiers)` returns
`(prompt_text, loaded_names, missing_identifiers)` and is the exact seam
`hermes -z "…" -s <name>` uses. Point `HERMES_HOME` at a throwaway home,
register the real skill dir into it with the script above, then call it:

```python
import os, subprocess, sys, tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp()) / "hermes-home"
subprocess.run([sys.executable, "scripts/hermes_skills_register.py",
                "--home", str(home), "--dir", "/repo/.hermes/skills"], check=True)
os.environ["HERMES_HOME"] = str(home)

from agent.skill_commands import build_preloaded_skills_prompt
text, loaded, missing = build_preloaded_skills_prompt(["issue-triage", "bot-unattended"])
assert missing == []
assert "issue-triage" in loaded
assert "## Rules" in text
```

Assertions worth keeping:

- `missing == []` and every requested name in `loaded` — resolution, not just a
  non-empty string.
- The skill's frontmatter `description` appears in `text` — its CONTENT reached
  the prompt, not only its name.
- The negative case: with an unregistered home, the same list returns
  `loaded == []`, every name in `missing`, and `text.strip() == ""`. That proves
  the registration is what makes the load work.

Run this test where hermes-agent is importable (its own Python 3.12 venv in
`agents-read`, or a dev host), NOT in a hermetic image without the package — and
fail LOUDLY when the import is missing instead of skipping.

## Gate design for skill-driven legs

A checker that scans the Makefile/scripts for `hermes -z` calls should fail on:

- a leg with no `-s` preload;
- a skill name that does not exist under `.hermes/skills/`;
- a `name:` in the skill's frontmatter that disagrees with its directory;
- a skill missing any of `## Inputs`, `## Output`, `## Rules`;
- an inline prompt over the budget (~400 characters after the pointer rewrite);
- the unattended contract pasted back into a prompt instead of the shared skill;
- a skill that no leg preloads (dead file);
- a returned old rules file (e.g. `scripts/fix_bot_rules.md`) still `cat`ed into a
  prompt instead of being preloaded as a skill.

A `--report` mode that prints every leg with its prompt size and preload list,
and every skill with its frontmatter, makes the gate's output reviewable.

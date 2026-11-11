---
name: git-repository-setup
description: Initialize git repositories in user-specified directory structures without improvising locations or adding unrequested files.
triggers:
  - "create a repo"
  - "initialize git"
  - "git init"
  - "set up repository"
  - "make this a git repo"
  - "repository/git path"
---

# Git Repository Setup

Initialize a git repository at the exact path the user specifies. Do not improvise locations or add unrequested files.

## When to use

When the user asks to create a git repository, initialize one, or set up version control for a directory. The user may specify a path explicitly or implicitly.

## Steps

1. **Identify the exact target path.** Parse the user's instruction for a specific path. If they say "in X", use `X`. If they name a folder like `repository/ghit`, that is the literal path relative to the working directory or home. Do not substitute `repo`, `project`, or any other name.
2. **Create parent directories if needed** with `mkdir -p`.
3. **Initialize git** in that exact location with `git init`.
4. **Configure user identity** if not already set (use a placeholder email/name or ask — do not block on this).
5. **Stop.** Do not create `README.md`, `.gitignore`, or any other files unless the user asks. Do not offer to add files, set up remotes, or commit changes.

## Pitfalls

- **Wrong location.** The most common failure is initializing `.git` in the home directory or a parent directory instead of the user's specified subfolder. Always `cd` into the exact target path before running `git init`.
- **Extra files.** Do not create `README.md` or other scaffolding unless explicitly requested. The user asked for a repo, not a project skeleton.
- **Extra offers.** Do not ask "want me to add more files, set up a remote, or structure it for a specific project type?" after completing the task. Just report the path and stop.
- **Assuming `~/repo` as default.** Never default to `~/repo`. Use whatever the user names.
- **Literal path interpretation.** "repository/git" means a directory literally named `git` inside a directory literally named `repository`. Do not substitute similar-sounding names like `ghit`, `repo`, or `project`. Use the exact words the user typed.
- **When the path IS the repo, not a container.** If the user wants a folder to hold future repositories (e.g., `~/git/`, `~/repos/`, `~/projects/`), do NOT run `git init` inside it. Just create the directory. The `.git` folder should only exist inside an actual initialized repository.
- **Read the correction.** If the user corrects the path or intent, apply the correction immediately without defending or explaining. Profanity or frustration = wrong interpretation. Drop the previous approach entirely.

## Variant: repo WITH content, pushed to GitHub

When the user asks for a repo that ships files (README, LICENSE, code) AND is published to GitHub, the bare-init rules above do NOT apply — the user explicitly wants scaffolding and a remote. Use this flow instead:

1. `mkdir -p <path>` then `cd` into it.
2. Write the requested files (README, LICENSE, etc.) with `write_file`.
3. `git init -q && git add <files>`.
4. Commit with an explicit identity so it works on a fresh machine: `git -c user.name=<gh-user> -c user.email=<gh-user>@users.noreply.github.com commit -q -m "<msg>"`.
5. Create and push in one step: `gh repo create <name> --public --source . --push` (add `--private` for private). This sets the remote and pushes the current branch.
6. Report the repo URL from the command output — that is the deliverable.

Pitfalls:
- **Verify `gh auth status` first** — `gh repo create --push` fails silently-ish if not authed; the token needs `repo` scope.
- **The LICENSE text is easy to corrupt** when written by hand — a garbled final line (e.g. "permissions andand limitationsons") is a classic. After writing a long boilerplate license, read the last few lines and fix any doubled/merged words before committing. Prefer copying the canonical Apache/MIT text verbatim.
- **`--source .` requires being in the repo dir** — run from the repo root, not the parent.
- **Default branch is `master`** unless you set `--initial-branch`; that's fine, just don't claim `main`.
- **Curated-list repos: don't republish someone's curation as your own.** When the repo is a list compiled from a specific person's public commentary (e.g. "models X commented on") but the user wants that person unmentioned, do NOT scrape/replicate their picks and present them as yours. Compile from independent public sources and attribute each item to its actual creator, or ask the user to supply the items. State plainly that you did not lift the source's feed.

## Verification

After initialization, confirm with a one-line response:

    Git repository initialized at <exact-path>

Do not show `git status`, file lists, or other output unless asked.

## References

- `references/session-2026-09-11.md` — transcript of path-correction session that established this workflow.

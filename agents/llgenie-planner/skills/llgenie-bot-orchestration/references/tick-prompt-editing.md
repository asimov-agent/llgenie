# Editing the live orchestrator tick prompt

The tick's behaviour lives in a cron job's `prompt` field
(`$HOME/.hermes/profiles/<profile>/cron/jobs.json`), and that same text must be
versioned in the repo tree (the tick prompt is a committed file with a drift
gate). So a prompt change is TWO pieces: edit the live job, then file the
versioning issue. A live-only edit is invisible to the next reader and to CI.

## Procedure

1. **Locate the job and dump the prompt to a file** — never paste 15–20 KB into a
   shell literal.

   ```bash
   J=$HOME/.hermes/profiles/llgenie-planner/cron/jobs.json
   python3 -c "import json;d=json.load(open('$J'));print([(j['id'],j.get('name')) for j in d['jobs']])"
   python3 -c "import json;d=json.load(open('$J'));print(d['jobs'][0]['prompt'],end='')" > /tmp/prompt.txt
   ```

2. **Make a TARGETED edit, not a rewrite.** Find a unique anchor phrase already
   in the step you want to extend, assert it occurs exactly once, and insert the
   new sub-step after it. A full rewrite risks silently dropping a standing rule;
   a unique-anchor replace keeps the rest byte-identical.

   ```python
   p='/tmp/prompt.txt'; t=open(p).read()
   anchor="  6c. ...last line of the existing step...\n"
   add="  6d. YOUR NEW STEP TEXT ...\n"
   assert t.count(anchor)==1, "anchor not unique — pick a longer unique snippet"
   open(p,'w').write(t.replace(anchor, anchor+add))
   ```

3. **Apply it:** `hermes cron edit <job_id> --prompt "$(cat /tmp/prompt.txt)"`.
   The other flags (`--schedule`, `--skill`, `--model`, `--deliver`, …) are in
   `hermes cron edit --help`. If several `--prompt` edits must chain, edit the
   file in `/tmp` between calls rather than re-dumping.

4. **Verify on-wire — never trust the edit's exit code.** Re-read `jobs.json` and
   confirm the new marker, the char count, `enabled`, and `next_run_at`:

   ```bash
   python3 -c "import json;d=json.load(open('$J'));p=d['jobs'][0]['prompt'];print('marker:', '<unique new phrase>' in p, '| chars:', len(p), '| enabled:', d['jobs'][0]['enabled'], '| next:', d['jobs'][0].get('next_run_at'))"
   ```

5. **Version it in-repo.** File a six-section issue whose acceptance criteria
   cover BOTH halves: (a) the committed tick prompt gains the new step and reads
   through the drift gate, and (b) any skill reference the step cites is copied
   from the live profile into `agents/<profile>/` with its SKILL.md anchor. Route
   it to the documentation lane. A live-only behaviour change that never reaches
   the tree is the failure this step exists to prevent.

## Pitfalls

- **A prompt edit that quotes/backticks heavily must be passed via
  `$(cat file)`** — a `--prompt "..."` string with embedded quotes or `${...}`
  is mangled by the shell. Dump → edit file → `--prompt "$(cat file)"`.
- **Confirm the job survived `enabled: true`.** A syntactically valid edit that
  flips the job disabled (or loses `--skill`/`--schedule`) is a broken tick that
  still "succeeded". Read `enabled`, `next_run_at`, and `skills` back.
- **The change is not done until both pieces exist.** Live job edited AND
  versioning issue filed. Report both; a prompt that exists only in `jobs.json`
  cannot be diffed, reviewed, or drift-gated.
- **If the prompt grew a new mandatory step, prove it fired.** A later tick's
  output should show the new step's effect (e.g. cards created, a count change) —
  the step being present in the prompt is not proof it runs.

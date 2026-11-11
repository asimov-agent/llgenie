# LLM-driving pipeline: guaranteed facts

Facts the user re-confirms every session. Verify against the repo when asked, but
these are stable and documented.

## The model is pinned per RUN, not per image

- One place sets the model: `make _setup` runs `hermes config set
  model.aliases.<alias>.{model,provider,base_url,key_env,max_tokens,context_window}`
  from single Makefile vars, and it runs **inside the container, in the same
  container as the `hermes` call**, reading the bind-mounted repo. Every agent
  target starts with `_setup`; workflows never call Hermes directly, only `make`.
- **So a model-pin change needs NO image rebuild and triggers none.** The image
  is tagged on the Dockerfile's content hash; a Makefile-only change leaves that
  hash identical, and the build job logs `Image already current — skip rebuild`.
  When asked "is the new model in the deployed image?", the answer is that the
  model was never in the image — point at the run's own `model-caps` + Hermes
  routing-smoke steps (green after the pin merged) and at the build job's skip line.
- **Pin the DATED snapshot, never the floating family alias.** The endpoint often
  serves both (`<family>-<MMDD>` and the bare family id, plus `:batch` / `:US`
  variants). An alias can be repointed under a published image, an unchanged tag
  and a measured token budget, so nothing in the repo records that the model
  changed. Bump to the dated id and add a guard that fails when the pin equals the
  undated alias.
- Correct a wrong model id instead of agreeing with it — the family and date
  suffixes get mis-remembered across sessions.
- Every `hermes -z "…"` call passes `-m <alias>` on the SAME logical command (a
  dropped `\` splits it off and runs the model flags as a separate command with no
  alias → routes to whatever provider key is in env, e.g. Hugging Face → HTTP 403).
- Reasoning: search legs and the routing smoke run `--reasoning none`; the fix loop
  runs `--reasoning low`. Output cap is the model's real ceiling
  (`HERMES_MAX_TOKENS`, 65,536) — a larger `max_tokens` is clamped SILENTLY.
- `make model-caps` is the live gate that the endpoint serves this model and that
  the cap and reasoning-off settings hold; it runs before every refresh search and
  in every PR's live checks. Changing the pin must re-verify cap + reasoning (a
  test enforces this).
- **A live check cannot be run without the key — say so instead of claiming the pin
  is proven.** The PR's `live-smoke` job (`model-caps` + routing smoke) is the proof;
  name it as the verification and treat a red live-smoke as "the endpoint refuses
  this id, revert the pin".

## What the image DOES carry (so "latest agent" is a different question)

- The Hermes CLI, installed at build time through ONE installer seam from
  `HERMES_INSTALL_URL` — a **URL, not a version**, so two builds of the same
  Dockerfile can ship different CLIs.
- The pinned plugins (by commit) and the Python deps.
- Rebuild triggers: the hash tag is unpublished, **Sunday**, or an owner dispatch
  with `force_rebuild=true`. Otherwise the pipeline pulls the published base, so
  "update the agent" means dispatching a rebuild — never editing a Makefile var.
- The build also writes the alias and runs the alias check, so an image whose baked
  alias disagrees with the Makefile fails the BUILD, not a bot run.

## The daily schedule

- `refresh-bot.yml`: TWO crons — `"0 6 * * *"` and a backup on an odd minute
  (`"43 17 * * *"`). The guard lets the schedule through (only manual starts are
  staff-gated).
- **GitHub does not guarantee scheduled runs.** Its docs: the `schedule` event can
  be delayed under load and queued jobs can be dropped. A run can start hours late
  (observed ~5 h after its slot) or never appear — with no notification and no
  retry. A missing run is not a workflow failure; check the schedule-event runs
  before assuming, and judge staleness by the ARTIFACT's timestamp, not by a run row.
- Odd-minute crons dodge the :00 rush; a second slot far from the primary is the
  backup. `concurrency` queues the two if they overlap, and a manual dispatch while
  one is active queues behind it — dispatch ONCE, never launch a parallel run.
- **GitHub disables scheduled workflows after 60 days with no repo activity** in a
  public repo. Merging the daily PRs counts as activity. Re-enable with
  `gh workflow enable refresh-bot.yml`.
- Each run opens a PR only when there is new data; the PR still needs a merge.

## Overlapping refresh runs

When two runs overlap they can open competing PRs minutes apart. Distinguish which
RUN produced a PR by `createdAt` / the head branch's `-HHMM` suffix — never assume
the newest run owns the newest PR.

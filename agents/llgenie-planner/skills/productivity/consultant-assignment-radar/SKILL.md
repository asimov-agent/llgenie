---
name: consultant-assignment-radar
description: Use when Andy asks for fresh Stockholm consultant jobs.
version: 2.1.0
author: Hermes (for Andy Holst)
license: MIT
metadata:
  hermes:
    tags: [jobs, consultant, broker, stockholm, devsecops]
    related_skills: [obsidian, product-price-monitor]
---

# Consultant assignment radar (Andy Holst)

## When to Use

Load and run this skill when Andy asks:

- "what assignments / jobs exist for me right now"
- "check the brokers / konsultmäklare"
- "any new konsultuppdrag matching my CV"
- "jobs from the last 24 hours"

Run it end-to-end every time (scan → per-assignment files in `~/assignments/` → short summary);
never answer from memory or a previous scan.

## Defaults (apply without being asked)

- **Window:** last 24 h — only assignments at most one day old.
- **Location: Stockholm.** If Andy names no location, always filter to region **Stockholms län**
  (JobTech region concept `CifL_Rzy_Mku`). A posting counts as Stockholm when the text names Stockholm/Solna/
  Södertälje/Danderyd/Nykvarn/Sundbyberg **or** the location is location-agnostic ("Remote"/"Distans" alone).
  "Sundsvall (90% remote)" does **not** count. If he names another city/region, use that instead.
- **Output: one markdown file per assignment in `~/assignments/`**, named
  `<creation-timestamp>-<role-slug>.md` (`2026-10-13T121407-backend-engineer.md`).
  Sources that publish only a date get `2026-10-13T000000-unknown-time-<slug>.md`.
  Each file: role, created/published timestamp, source/broker, client, location, engagement
  (start–end, %, SEK/h), deadline, **link to the assignment page**, why it matches the CV, and the
  source's description body.
- **Working data: `~/.local/share/consultant-radar/`** (`JOB_RADAR_DATA` overrides). Every script defaults
  there. **Never write inside `~/repository/git/`** — that directory holds Andy's real source repositories;
  a `job-radar/` folder there looks like a repo he did not create, and he does not want it. Nothing in this
  workflow is ever published: no `git init`, no remote, no push, no upload.
- Clear stale files first: `rm -f ~/assignments/*.md` before a fresh run.
- Then a terse chat summary: top matches by tier + what was blocked/gated, with real counts
  (ads in window, matches, files written).

## CV match profile — `scripts/andy_keywords.py` is the single source of truth

Every assignment is scored with Andy's own vocabulary, not a hand-wave. `andy_keywords.GROUPS` holds his full
competency list grouped into 15 areas, each keyword with alias spellings (Swedish/English), e.g.

| area (weight) | keywords |
|---|---|
| DevSecOps / DevOps / CI-CD (3) | DevSecOps, DevOps, CI/CD, pipelines, Jenkins, GitHub Actions, GitLab CI, Argo CD, GitOps, Dagger |
| Cloud & platform, AWS-heavy (3) | AWS incl. Lambda/Fargate/S3/EC2/RDS/VPC/Route 53/ELB/SQS/SNS/CloudWatch/Kinesis, boto3, Azure, GCP, serverless, FinOps |
| Kubernetes & containers (3) | Kubernetes, Rancher/RKE, OpenShift, Helm, Docker, Podman, OCI images, Kustomize, service mesh |
| Infrastructure as Code (3) | Terraform, CloudFormation, Ansible, IaC, golden paths, platform engineering |
| Security engineering (3) | security/appsec/cyber/infosec, IAM, OAuth2/OIDC, Zero Trust, PKI-TLS-CA, OpenSSL, vulnerability scanning (Trivy/Grype/Syft/Anchore/Snyk), pentest tooling, SIEM/SOC/Sentinel, compliance (ISO 27001/NIS2/GDPR), SonarQube, Vault |
| Agentic & Generative AI (3) | agentic AI, LangChain/LangGraph, LLM, GenAI, RAG/vector DB, prompt engineering, Copilot/OpenCode/Kiro harnesses, MLOps, ML, AI governance/AI Act, inference servers (Ollama, llama.cpp, vLLM), Hugging Face, spec-driven development/OpenSpec |
| Solution architecture / Tech lead (3) | solution/IT/system/enterprise/infrastructure/integration/security architect, tech lead, systems engineering, requirements + architecture as code, microservices, monolith→microservices, REST/GraphQL/OpenAPI, event-driven/Kafka/JMS |
| Backend Java & Python (2) | Java, Spring Boot, Java EE/Jakarta, Kotlin, Python, FastAPI, Flask, Groovy, Perl, C++, bash, Maven/Gradle/Makefile, Node.js, JS/TS, JBoss/WildFly/Tomcat/WebSphere |
| Data & persistence (2) | PostgreSQL, MySQL, Oracle, DB2, Neo4j, JPA/Hibernate, Liquibase/Flyway/Alembic, SQL, Kafka, Redis, MongoDB, data engineering (Spark/Flink/ETL/Databricks) |
| Observability (2) | Prometheus, Grafana, Kibana/ELK, Datadog, monitoring/telemetry, tracing/OTel |
| Testing & quality (2) | TDD/BDD, JUnit/Mockito, Testcontainers, test automation, coverage, code reviews |
| Frontend (1) | Angular, React, HTML/CSS |
| Ways of working (1) | Agile/Scrum/Kanban/SAFe, requirements analysis, docs-as-code, C4/PlantUML, Jira/Confluence, Linux/OS, Git/GitHub/GitLab/Bitbucket, Renovate/Dependabot, public-sector experience |

Scoring: `score_text()` returns matched keywords per area plus a weighted score (area weight × distinct
keywords, capped per area so one noisy area cannot dominate) and `coverage()` counts the 7 core (weight-3) areas.
Thresholds: **≥8 points and ≥2 areas** to be written at all; **≥30 = high**, **≥16 = medium**, else low fit.
`NOISE` / `EXCLUDE_HEAD` drop non-CV headlines (care, construction, iOS/Android, pure frontend, .NET-only,
automotive/embedded/ASIC, sales) even when keywords leak into the text.
Extend the keyword lists whenever Andy adds a technology to his CV — never hard-code keywords elsewhere.

## Stage 1 — dated backbone: Platsbanken (JobTech Search API, no key, exact timestamps)

```bash
python3 scripts/scan_platsbanken.py 24                      # -> ~/.local/share/consultant-radar/*.json
python3 scripts/scan_platsbanken.py 48 "$HOME/.local/share/consultant-radar" <region-id>   # other window / region
```

Raw query shape (use curl — urllib intermittently gets spurious 400s):

```
https://jobsearch.api.jobtechdev.se/search?limit=100&offset=0&sort=pubdate-desc\
  &published-after=<ISO-UTC>&region=CifL_Rzy_Mku
```

- `published-after` = `YYYY-MM-DDTHH:MM:SS` **UTC**. `offset` **hard caps at 2000**; beyond it the API answers
  400 (`"2100 is not less or equal to 2000"`). Fill the tail by re-paging with `occupation-field=<concept_id>`
  shards taken from ads already fetched — and only then declare the window complete.
- Verify the region id once per session by fetching one hit and checking `workplace_address.region`.
- Score locally against `andy_keywords`; the API's free text is noisy, so never trust `q=` alone.
- **Employment-type gate (do not skip this).** Platsbanken is full of employment positions; Andy takes
  assignments only. `is_assignment()` drops every ad whose `employment_type` is any form of employment — the regex
  matches the word *anställning* itself (vanlig, tillsvidare, heltids-, prov-, behovs-, tidsbegränsad and
  timanställning all go) plus *vikariat, säsongsarbete, sommarjobb, feriejobb, extraarbete, trainee, lärling,
  praktik*. Only *frilans / egen konsult / underkonsult / konsultuppdrag / uppdrag* survive. The run prints how many
  CV-matching ads the gate removed, so the loss is visible rather than silent.
- Expect the gate to empty Platsbanken: in a 24 h Stockholm window it removes essentially every CV match (53 of 53
  on 2026-10-14). That is the correct result, not a fault — Platsbanken is an employment board. **The assignments
  live on the broker marketplaces**; say that plainly instead of padding `~/assignments` with employment ads.
- Each match row keeps everything the writer needs: employer (+org.nr, url), workplace + coordinate-level
  address, occupation taxonomy, employment type, working hours, scope, duration, salary, vacancies,
  experience required, apply-by, apply URL/email, application contacts, must-have/nice-to-have blocks
  (skills, experience, education, languages) and the full ad text.

## Stage 2 — broker sweep: cover the WHOLE registry, never an ad-hoc list

`references/broker-registry.json` holds every Swedish konsultmäklare/marketplace the public registers know of
(149 actors, de-duplicated by host) — built from Anna Leijon's konsultmäklare list and Kretsia's guide.
Refresh it a few times a year, or when a name is missing:

```bash
python3 scripts/build_broker_registry.py     # rewrites references/broker-registry.json
```

Sweep it in slices. The deterministic first pass is scripted:

```bash
python3 scripts/probe_broker_slice.py 0 20 24 /tmp/slice0.jsonl     # <from> <to> <hours> <outfile>
```

It fetches each broker's portal, follows up to 12 same-host listing links and extracts only machine-readable
publication times (Teamtailor JSON-LD `datePosted`, Cinode `Announced 13 Oct, 2026`, WordPress `published`,
relative "12 hours ago"), writing one JSON record per broker plus one per fresh item — always with the verbatim
evidence string. Brokers whose list is JS-only or gated come back as `open_items_no_date` / `no_public_list`.

Then cover the rest: for every slice where the script found nothing machine-readable, open the portal in the
browser (`new_tab`/`wait_for_load`/`js('document.body.innerText')`, 3–6 s waits). For breadth, `delegate_task`
5 parallel batches over the registry slices — each child works its own slice, appends JSONL to its own file so a
timeout loses nothing, and returns the same record shape. Per-broker status vocabulary, used verbatim in the
final table: `fresh_items` · `open_items_no_date` · `login_gated` · `no_public_list` · `blocked` · `js_or_gated` · `dead`.

Merge the sweep files back with validation, then report coverage:

```bash
python3 scripts/merge_broker_sweep.py "$HOME/.hermes/cache/scratch/broker_sweep_*.jsonl" 24
```

It keeps only in-window, Stockholm/remote items that score ≥ 8 points across ≥ 2 CV areas (login-walled sources
like Ework/Verama use ≥ 3 points on title + end customer instead, with the lower evidence bar recorded in the
finding), re-scores short sweep snippets against their fetched detail page before rejecting them, drops any link
that is not HTTP 200, appends the survivors to `broker_findings.json` without duplicating links, and writes
`sweep_coverage.json` — the per-broker status table quoted in the final report.

It must read **both** JSONL and pretty-printed JSON arrays/objects — subagents return either, and a reader that
only understands JSONL silently loses an entire slice. It also rewrites the coverage statuses: a broker counts as
`fresh_matching_items` only when one of its in-window items actually passed the CV filter and landed in
`broker_findings.json`; a broker that published in-window but nothing CV-matching is `fresh_but_off_profile`
(doctors, sales, content roles) — worth knowing, never worth a file in `~/assignments/`. Re-runs count the earlier
sweeps' findings as accepted, otherwise every re-run would downgrade the table.

**A child's summary is not a record.** One batch claimed 16 brokers but its file contained 4; the missing 12 were
re-probed with `probe_broker_slice.py` before any status was reported. Always diff the file against the summary and
verify the brokers the summary claims but the file lacks.

**Merge pitfalls (each one silently lost a whole slice before it was fixed):**

- **Subagents return three different shapes — JSONL, a pretty-printed JSON array, and pretty-printed
  consecutive objects — and a reader that only handles one silently drops the other two.** The merge's
  `read_records()` must accept all three (a streaming `JSONDecoder().raw_decode` loop that also unwraps lists),
  or a batch that wrote an array comes back as "0 parseable" and its brokers vanish from coverage.
- **Date-only timestamps must be judged per-day, not at 00:00.** An item stamped `2026-10-13` (no time) was being
  discarded as outside a 24 h window because it compared as midnight. Compare the *date* against the window start
  date, then write it `unknown-time` — never drop it for lacking a clock time.
- **A short sweep snippet under-scores a real assignment.** A 1–2 sentence card (title + client) can score below
  the ≥8 threshold even when the full ad is a strong match. Before rejecting anything, fetch the detail page and
  re-score on the page text; only reject if the enriched score still fails. Login-walled sources (Ework/Verama)
  use the lower `score ≥ 3` bar instead — never reject a gated item for having an empty snippet.

Handing work to subagents: tell every child to append its JSONL as it goes (a timeout must not lose a slice), to
**keep its final answer under ~15 lines** (children that narrate their findings hit the output-token limit and
return nothing at all — that is how one batch was lost), and to time-box each broker to ~90 s, spending the rest
on the ones that publish dates. Re-dispatch any failed slice immediately instead of waiting for the batch.

Report coverage explicitly: "N of 149 registry actors probed, M fresh, X undated, Y gated, Z blocked/dead".
An unanswered broker is a hole in the deliverable — say which ones and why, and never let a subset of ~20
portals masquerade as "the brokers".

### Known per-source mechanics and gotchas (cheat sheet)

| Broker | Where | Freshness signal | Gotchas |
|---|---|---|---|
| Ework / Verama | `app.verama.com/en/job-requests` | relative age ("14 hours ago") | guests see ~20 of ~199; details behind login |
| Cinode Market | `cinode.com/market/` | **"Announced 13 Oct, 2026"** per card | click "Load more" until it disappears; deeper results need a free account |
| Brainville | `brainville.com/en/RequisitionSearch?Text=<kw>` | "yesterday 16:06" | only a 5-item sample without an account — run many keyword searches, dedupe by `Requisition?id=` |
| Tingent | `tingent.se/jobs` | `requisition_publisheddateandtime` in the embedded HTML JSON | parse the HTML, not the DOM list |
| Regent | `regent.se/uppdrag/<id>` | `publishedAt` in the detail page JSON | the list page carries no dates |
| KeyMan | `keyman.se/uppdrag/` | `2026-10-13` date next to each item | dates sit in text, not markup |
| Nikita | `nikita.se/lediga-uppdrag/` | "9 Oct" per row | date only, no time |
| Epico | `jobs.epico.se/jobs` (Teamtailor) | `datePosted` in each job page's JSON-LD | list page shows no dates |
| Senterprise / Great IT | `jobb.*.se` (Teamtailor) | `datePosted` on detail pages | some department pages expose no `/jobs/<id>` links |
| House of Skills | `houseofskills.se/category/konsultuppdrag/` | WordPress `published">2026-10-13` | — |
| SeeQualy, Levigo, Profinder, Witted, Jappa, Resursbrist, Iceberry, Tech Relations | own sites | usually none | extract current openings, label "date not published" |
| Onsiter | `onsiter.com` | — | Cloudflare-blocked for automation — hand the link to Andy |
| emagine SE | `emagine-consulting.se` | — | no public SE assignment list |
| Cinode deeper pools, Keyed, Upgraded, Experis | portals | — | login-gated: say so, never guess |

Browser recipe: `new_tab(url)` → `wait_for_load()` → `time.sleep(3-6)` → read `document.body.innerText`; for lists
extract links plus their nearest text in one `js()` pass. Save captures to the workspace as you go (a timeout
must not lose progress) and append findings to JSON, aggregating in Python rather than by eye.

**Parsing traps that have bitten before**

- Card text is positional: `"yesterday 16:06 | <title> | <location> | …"`. Do not assume `parts[1]` is the
  location — match the first field against a place regex (Stockholm/Solna/Stockholms län/Remote/…) instead.
- Relative ages ("17 hours ago") must be converted to an absolute timestamp at capture time, then re-checked
  against the window; a 24 h window shifts every run.
- Teamtailor detail pages sometimes drop their JSON-LD `datePosted`; if it is gone, fall back to the date you
  verified earlier in the same run or mark the item `unknown-time`.
- Turn the captures into `broker_findings.json` with the packaged builder, then eyeball its printout before
  emitting — a location/title swap is invisible in the output files but wrong in every one of them:

```bash
python3 scripts/build_broker_findings.py "$BH_AGENT_WORKSPACE" 24   # -> job-radar/broker_findings.json
```

## Stage 2.5 — enrich every finding from its own detail page

A list card is not an assignment. Fetch the detail page of each kept finding and score the *page text*:

```bash
python3 scripts/build_broker_findings.py "$BH_AGENT_WORKSPACE" 24   # -> job-radar/broker_findings.json
```

| Source | How the detail is obtained |
|---|---|
| Cinode Market | `curl https://cinode.com/market/requests/<id>` — server-rendered: full requirements, utilisation, period, last day to apply |
| Regent | `curl https://regent.se/uppdrag/<id>` — full "Om uppdraget" text |
| KeyMan | listing text gives the slug → `curl https://www.keyman.se/sv/data-it/<slug>/` |
| House of Skills | `curl` the post URL from the category page |
| Tingent | full requisition JSON is embedded in `tingent.se/jobs` (`requisition_description`, `requisition_skillset`) |
| Brainville | the requisition body is JS-rendered and partly gated — open each `Requisition?id=` in the browser (loop, ~4 s each) and keep title, region, days left, skill tags, location, duration; the description itself needs a free account |
| Ework / Verama | description + rate are behind the free Verama login — record that explicitly, never invent a rate |

Each enriched finding then carries: role, official posting timestamp, broker, end customer, location, engagement,
rate, deadline, contact, link, skill tags, description text, the matched keyword list per area with points and
core coverage, and a provenance line stating where the timestamp and text came from.

**Filter dynamically, never with hand-maintained id allow-lists.** Every source follows the same rule: in-window
+ Stockholm/remote → fetch the detail page → keep only if `score ≥ 8` and `≥ 2` CV areas match. Exception: sources
whose description is behind a login (Ework/Verama) are scored on title + end customer and kept from
`score ≥ 3`, with the provenance line saying so — dropping a perfect "Cyber Security Engineer (H&M)" because the
text is gated would be worse than keeping it with a documented lower evidence bar.

## Stage 3 — emit the per-assignment markdown files

```bash
rm -f ~/assignments/*.md
python3 scripts/emit_assignments.py 24    # -> ~/assignments/<timestamp>-<slug>.md
```

Data directory resolution: the emit script reads `~/.local/share/consultant-radar/` (override with
`JOB_RADAR_DATA=...`), falling back to its own directory. It needs `broker_findings.json` there alongside the
scan output. It also re-checks every broker link: a 404/410 (assignment withdrawn) drops the finding, and a
`000` from curl (site WAF) is noted in the file rather than reported as dead.

Each written file is a full briefing, not a one-liner:

1. **Key facts** — posting timestamp, source/broker, assignment-page link, employer/end customer (+org.nr, url),
   workplace, location, occupation taxonomy, engagement (employment type, hours, scope %, duration), salary/rate,
   vacancies, experience required, apply-by, apply URL/email, contact persons.
2. **CV match (Andy Holst)** — points, keyword count, areas covered, core coverage n/7, then the matched
   keywords listed per CV area with their points, plus the core areas the ad does *not* mention.
3. **Requirements** — the ad's must-have/nice-to-have blocks (or the broker page's skill tags).
4. **Full description** — the complete ad text (truncated at 6 000 chars with a marker).
5. **Provenance** — window, region, API/board, the exact field the timestamp came from, and the scoring profile used.

Afterwards verify the folder before summarising: file count and source counts, every file carrying a `points` fit
line, **no** location outside Stockholm/Remote, and `curl -o /dev/null -w '%{http_code}'` = 200 for every unique
assignment link.

Reads `job-radar/platsbanken_matches.json`, `platsbanken_raw.json` and `broker_findings.json` (broker findings
are transcribed from the stage-2 captures: created, source, role, client, location, engagement, deadline, link,
fit, fit_note). Keep only Stockholms län (or the location Andy named); "Remote" is kept and marked. Regenerating
is idempotent and filenames carry creation timestamps so the folder sorts chronologically.

## Rules

- Never state a posting time the source did not give — date-only sources are written `unknown-time`.
- Never write a link you have not verified (`curl -s -o /dev/null -w '%{http_code}'`).
- Report blocked/gated sources explicitly; silence reads as "nothing there".
- Verify by counting: ads in window → matches → files written, and re-read a sample file before reporting.
- Scratch and JSON stay in `~/.local/share/consultant-radar/`; `~/assignments/` holds findings only. Never create
  files or folders under `~/repository/git/` (his source-repo tree) and never publish this work anywhere.
- **Breadth is the deliverable.** A run that probed 20 portals when the registry lists 149 is incomplete, not
  "nothing there". Sweep the registry slices, keep every per-broker status, and publish the coverage counts.
- Timestamps, links, rates and clients are only ever copied from the source, with the evidence string kept in
  the finding; a login wall or a Cloudflare block is reported as such — never filled in with a plausible guess.

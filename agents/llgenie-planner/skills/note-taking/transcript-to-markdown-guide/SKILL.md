---
name: transcript-to-markdown-guide
description: Use when turning a transcript into a markdown guide.
version: 1.1.0
author: Hermes Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [markdown, reference-guide, transcript, verification, kubernetes, docker]
    related_skills: [obsidian]
---

# Transcript → Detailed Markdown Guide

Turn a raw transcript (lecture, video, talk) into a polished, comprehensive markdown reference file. The user asks for "detailed markdown file based on this transcript" — this is the exact workflow.

## When to use
- User pastes a transcript and asks for a detailed markdown file/guide from it.
- User asks to document a technical topic (Kubernetes, FastAPI, React, etc.) as a reference guide.

## Workflow

1. **Read the transcript fully** and extract the core technical facts. Do NOT just reformat the transcript — expand it into a proper reference.
2. **Structure with a Table of Contents** (numbered sections). The user explicitly asks for `##` markdown headings — every section must be a `##` heading (TOC, each topic, cheat sheet).
3. **Cover these sections** (adapt to topic):
   - What is X / fundamentals
   - Key concepts & analogies (keep the transcript's own analogies — e.g. the ID-card/barcode token analogy)
   - Setup / installation
   - Core usage with **code blocks** (imperative + declarative where relevant)
   - A **"<field|flag|option> → the manual command it replaces"** mapping section. This is the highest-value section in any configuration lecture: `isGateway: true` → `ip addr add`, `ipMasq: true` → `iptables -t nat -A POSTROUTING -j MASQUERADE`, `--service-cluster-ip-range` → the VIP pool. It turns a list of YAML keys into understanding, so add it even when the transcript only defines the fields.
   - Best practices (Do/Don't, or a dedicated section)
   - A **full runnable example** at the end
   - A **summary / cheat sheet** table
4. **Use tables** for comparisons (e.g. user vs service account, method→CRUD, type→use).
5. **Add what the transcript omits but the topic requires.** Flag this explicitly to the user. Example: the service-account transcript never mentioned RBAC, yet a SA is useless without a Role/RoleBinding — I added that section and told the user it was a gap.
6. **Write to the home folder** (`$HOME/`) with a descriptive name like `<Topic>_Guide.md` unless the user says otherwise.
7. **This is a batch pattern** — the user often sends several transcripts in sequence, each producing its own separate guide file. Treat each transcript as an independent deliverable with its own filename; do not merge them into one file.
8. **One call to write, then two scripted probes.** Big guides run 20–40 KB; write the whole file in a single `write_file`. Then run, in this order:
   - `scripts/verify_guide.py <file> [...]` — structure, block syntax (bash/json/yaml), TOC anchors under GitHub slug rules, rectangular tables, and unquoted `<placeholder>` pasteability.
   - `scripts/claim_coverage.py <file> <claims>` — one distinctive string per load-bearing transcript fact (a port, an object name, a phrase the section hinges on), case-insensitive. This is the only probe that catches a guide which passes every structural check and still dropped half the lecture; build the list while reading the transcript.
   Report both numbers ("17 sections, 29 bash blocks clean, 24/24 claims") and stop. Do not iterate section by section.
   Re-running a guide you produced in an earlier turn: `write_file` refuses to overwrite a file this task has not fully read, so `read_file` it whole first, or `patch` the specific sections instead.

## Output conventions
- Filename: `/<Topic>_Fundamentals_Guide.md` or `/<Topic>_Guide.md`.
- Every code block is complete and runnable, not a stub.
- Tables for any comparison.
- A "Best Practices" section with concrete rules.
- A "Full Runnable Example" section.
- A summary/cheat-sheet table at the end.
- In a lecture series, name each guide by its own topic so the set reads as a set (`Docker_Networking_Guide.md`, `CNI_Guide.md`, `Kubernetes_Node_Networking_Guide.md`) and open with one line saying what the previous guide covered — the user is building a sequence, not collecting files.
- A closing "one-paragraph mental model" under the cheat sheet: the whole topic compressed into 4–6 sentences, so the guide is re-readable in ten seconds.

## Pitfalls
- **Transcripts are ASR output, not source code.** Spoken commands arrive mangled — `ip net n s`, `v eight`, `ip l e d r`, `one ninety two one sixty eight fifteen dot one`. Never copy that spelling into a code block: reconstruct the real syntax (`ip netns`, `veth`, `ip addr add`, `192.168.15.1`), then make every address in the guide mutually consistent (a gateway, the host IP, the subnet) instead of transcribing each garbled number separately. List the normalisations in the report as one line.
- **Spelled-out digits and mangled proper nouns need the same treatment.** "six four four three" is `6443`, "one zero two five zero" is `10250`, "thirty thousand to thirty two thousand seven sixty seven" is `30000–32767`; "cube control tool" is `kubectl`, "hcd server" is `etcd`, "rocket" is `rkt`, "brids" is `bridge`. Rebuild the term from the domain, never from the phonetics, then say what you normalised in one line. Never let a spoken number become a literal port or address in a table — a wrong port is the most damaging error a networking guide can carry.
- **A lecture's numbers can be a version-specific default, and lecturing prose is not authoritative.** Check every port/version/flag against the current upstream default before writing it down (secure vs insecure control-plane ports, deprecated read-only ports, renamed commands) and, where it changed, write both: the current default plus the older value the speaker is describing. Cite the upstream doc page name rather than inventing a URL.
- **A lecture's product list ages faster than its concepts.** Before naming a tool, service or vendor from an older recording, check it still exists and still does what the lecture says. Keep the product, add its current name (`Container Engine` → `GKE`, `ECS for Kubernetes` → `EKS`), and where something was retired or superseded put that in a status table (the guide is read long after the recording). Prefer the *mechanism* over the brand — "managed control plane", "kubeadm-family bootstrap" — because brands churn and mechanisms do not.
- **Correct the lecture's own errors, and say so in a table.** Collect them under a `## Gaps and Corrections` section as `# | transcript says | reality` rows (plus a second list of "additions not in the transcript"), and repeat the count in the report. Never silently fix and never silently repeat — a wrong rule stated confidently in a lecture is the thing a reader will quote back at you.
- **A transcript can be a lab walkthrough, not a lecture** (a demo that answers questions about a live system). Then keep its shape — one `##` per question, each written as *ask the API → confirm on the node* — and add the two things a demo cannot contain: the alternate command for when the primary fails, and why the answer counts as proof. Never narrate the presenter's mouse movement; the commands are the content.
- **The file is the deliverable, and live validation is opt-in because it mutates the user's host.** Default: static verification only — do not start clusters, containers or VMs unless the user asks for it or accepts your offer. When they do ask, ask before installing anything (a `~/.local/bin` binary, a cluster, image pulls count) and tear all of it down afterwards — recipe and cleanup checklist in `references/live-verification.md`. Leaving a kind cluster, a downloaded kubectl, `~/.kube`, or a temporary git worktree behind is the failure the user will call out as "undo whatever you did".
- **Static verification is one command, and it runs before you reply.** Use `scripts/verify_guide.py <file> [more.md ...]`, which checks structure (title, `##` count, fence parity, TOC anchors under GitHub slug rules, rectangular tables) **and** the syntax of every ```bash / ```json / ```yaml block, then quote its numbers in the report. Run it once over the whole batch before replying. If you could not execute anything, say plainly "I did not execute this" and why, instead of implying it was tested — and put that line **in the file** too, as a one-line note under the intro (commands reconstructed from the lecture, sample outputs illustrative, nothing run). The file travels without the chat, and a reader who trusts an unexecuted `iptables` rule is the cost.
- **Angle-bracket placeholders break a code block's pasteability.** `<pod>`, `<name>`, `<node>` at command position parse as shell *input redirection*, so `kubectl logs <pod> | head` is a syntax error and fails the moment a reader pastes it. Write the placeholder quoted (`kubectl logs "<pod>" | head`) or substitute a concrete example value, so the block parses and pastes as written.
- **A typed fence must contain a complete document.** Tagging a property fragment as ```json (an `"ipam": {...}` snippet lifted out of a config) produces a block that does not parse. Either wrap it in the smallest complete object that still makes the point, or tag the fragment ```text. Same for `---`-less YAML fragments.
- **Helm/Go template blocks are not YAML — tag them `gotemplate`.** Anything containing `{{ .Values.x }}` fails `yaml.safe_load` because it only becomes YAML after rendering, so tagging a `templates/*.yaml` excerpt as ```yaml is a real defect (hit twice in the Helm guides). Use ```gotemplate, and say in the prose that the block renders via `helm template` before it parses. The same applies to Jinja/ERB-style template excerpts in other ecosystems.
- **Escape `|` inside table cells.** `rp_filter=0|2`, `--initial-cluster-state new|existing`, or a shell pipeline written into a cell (`helm list | grep x`) splits the row into an extra column and silently corrupts the table. Write `\|` (and the same for any literal pipe inside inline code in a table).
- **Cross-check the domain, not just the syntax.** For networking/infra guides, extract every dotted quad and CIDR and classify it against the ranges the guide declares (pods, services, nodes): a pod IP appearing in the service range, or two documents quoting different cluster CIDRs, is the error class that survives every structural check. Cheap version: grep the addresses, then read only the lines that carry both a pod-ish and a service-ish word.
- **Check whether the transcript is one you already covered before writing a second file.** A re-sent lecture (the user pasting the same walkthrough again) must not become `<Topic>_Lab_Guide_2.md`: grep `~/*.md` for the distinctive object names from the transcript, and if a guide exists, say so, give its path and size, and offer concrete options (a one-page answer key, nothing, or the next transcript) instead of duplicating byte-for-byte work.
- **Don't invent facts.** Ground everything in the transcript; only add well-established standard material (RBAC, security) and label it as an addition.
- **Don't just reformat** — the value is in structure, expansion, and best practices.
- **Flag gaps** in the transcript to the user rather than silently filling them.
- Keep the user's preferred location in mind: they keep `~` clean and use `$HOME/repository/git/` for code — offer to move the file there if it's a code-adjacent guide.
- User communicates in Swedish — respond in Swedish when they write in Swedish.
- **When re-prompted to "verify", escalate to a check class you have not run — never fabricate a change.** The ladder, in order: (1) structure, (2) code-block syntax, (3) domain consistency (addresses/CIDRs/ports against what the guide itself declares), (4) cross-document agreement across the batch, (5) live execution of the guide's own commands against a throwaway cluster/daemon — the only class that catches a *version-stale default* inherited from an old lecture (a field that is now mandatory, an annotation that no longer fires without its precondition). Tier 5 needs the user's go-ahead and a teardown; never run it silently to satisfy a prompt. Each pass must be a genuinely different question; re-running the previous one is not progress. When a class passes, say so with the numbers and name what remains unverified (usually: nothing was executed). Then ask for one concrete assertion — a cluster/daemon to run against, a specific file and section — and stop. A generic "has not passed" with no assertion cannot be satisfied by editing files, and inventing a defect to have something to fix corrupts the deliverable.

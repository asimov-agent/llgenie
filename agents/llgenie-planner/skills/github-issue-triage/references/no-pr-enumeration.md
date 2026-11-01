# Enumerating the open issues that have no PR

One `gh` call per issue is the price of an honest answer. Batch it and persist the result, because open
issues move under you while you work.

```python
import json, subprocess
REPO = "<owner>/<repo>"
issues = json.loads(subprocess.run(
    ["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", "200",
     "--json", "number,title,labels,updatedAt,body"], capture_output=True, text=True).stdout)
rows = []
for i in issues:
    tl = subprocess.run(
        ["gh", "api", f"repos/{REPO}/issues/{i['number']}/timeline", "--paginate", "--jq",
         '[.[] | select(.event=="cross-referenced") |'
         ' {pr: .source.issue.number, prurl: .source.issue.pull_request.url}]'],
        capture_output=True, text=True)
    prs = [r for r in json.loads(tl.stdout or "[]") if r.get("prurl")]
    rows.append({"n": i["number"], "title": i["title"], "labels": [l["name"] for l in i["labels"]],
                 "prs": prs, "updated": i["updatedAt"]})
json.dump(rows, open("issues.json", "w"), indent=1)
for r in rows:
    if not r["prs"]:
        print(r["n"], "|", r["title"][:110], "|", ",".join(r["labels"]))
```

Notes:

- **The `pull_request.url` filter is the whole procedure, not a detail.** A `cross-referenced` event is
  written for issue→issue citations as well as for PRs, so a query that selects `source.issue.number`
  and not `source.issue.pull_request.url` reports "has a PR" for any issue that merely cites another
  one. It looks right and is wrong: measured on `asimov-agent/llgenie` (2026-10-27, 68 open issues) the
  unfiltered read shortlisted **17** candidates, the filtered one **26** — nine real ones were hidden.
  Print `len(live)` next to `.open_issues_count` before triaging and reconcile the two.
- `--limit 200` on a repo with more open issues silently truncates: check the count against
  `gh api repos/<o>/<r> --jq .open_issues_count` before believing the shortlist is complete.
- Keep `body` in the fetch: the log tail a bot filed is the evidence, and re-fetching 26 bodies one at a
  time later doubles the cost.
- Triage in batches of ~10 and append to the JSON file; a long single run is the one that times out.
- Sorting the shortlist by label first (`agent:implement`, then unlabelled) separates bot-filed run
  failures from human design issues, which need different verdicts.

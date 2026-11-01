"""Which two open issues describe the same defect — and closing the copy without losing the work (#551).

The refiner makes ONE issue implementable per run and the implementer implements ONE. Neither looks ACROSS
the backlog, so the same defect filed twice is implemented twice or, worse, the copy is implemented and the
better specification is retired. The implementer's `close` verdict only catches a duplicate it happens to
read; #400 -> #254 and #440 -> #399 were both retired that way, and until #521 the canonical issue was left
unlabelled, so the defect was queued nowhere.

This module is the cross-issue sweep, four times a day:

1. **Candidates are unprotected open issues.** An issue carrying any agent label is CLAIMED: the implementer
   owns `agent:implement`/`agent:ready`, the refiner's restatement is `agent:refined`, `agent:closed` ended its
   life, and `agent:duplicate` is already a closed copy. A claimed issue is never a candidate and never a
   target — the sweep cannot race the bots that do the work, and it never re-opens a decision.
2. **A pair is chosen deterministically** (shared significant tokens in title+body, Jaccard >= the threshold,
   the older issue as canonical). The pair, not a verdict, is what the agent leg is given.
3. **The agent decides** whether the two describe the same defect, and answers `DUPLICATE: #<older>` with an
   `EVIDENCE:` block naming what makes them the same. No evidence, no close: the same rule as the implementer.
4. **Closing retires the COPY only**: a comment citing the canonical issue and the evidence, the
   `agent:duplicate` label, then the close. The canonical issue is QUEUED (`agent:implement`) when it carries
   no queue label, so a duplicate close never loses the work.

`--dry` prints the decision and mutates nothing; the tests stub `gh` on PATH, the repo's allowance for an
external CLI.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot_claims  # noqa: E402  the shared protocol (issue #279)

#: A label that makes an issue CLAIMED: never a candidate, never a target (issue #551).
PROTECTED_LABELS = ("agent:implement", "agent:ready", "agent:refined", "agent:closed", "agent:duplicate")
#: The label put on the issue that is retired as a duplicate.
DUPLICATE_LABEL = "agent:duplicate"
#: The labels that put the canonical issue in front of the implementer.
QUEUE_LABELS = ("agent:implement", "agent:ready")
#: Jaccard similarity at which two issues are worth an agent's attention.
THRESHOLD = 0.30
#: Words that carry no signal for "is this the same defect".
STOPWORDS = frozenset(
    """a an and are as at be been being but by can could did do does for from had has have how i if in
    into is it its just like may might more most must my no not of on or our out over same should so some
    than that the their them then there these they this those to too under up use used using very was we
    were what when where which while who why will with would you your""".split())
TOKEN = re.compile(r"[a-z0-9][a-z0-9._:/-]{2,}")
#: A machine-generated tracker issue carries its generator's marker in the body (`<!-- architecture-bot:… -->`).
#: Those issues are near-identical BY CONSTRUCTION — every run says "refresh X for the tree at <stamp>" — so a
#: token comparison pairs them at 0.78 and asks the agent a question with no answer (measured: #494 <- #517).
GENERATED = re.compile(r"<!--\s*[a-z-]+-bot:", re.IGNORECASE)


def _gh(gh: str, args: list[str], token: str | None = None) -> str:
    env = None
    if token:
        import os
        env = {**os.environ, "GH_TOKEN": token}
    r = subprocess.run([gh, *args], capture_output=True, text=True, env=env)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[issue-dedup] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def labels(issue: dict) -> list[str]:
    return [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]


def is_protected(issue: dict) -> bool:
    """A claimed issue is never a candidate and never a target (issue #551)."""
    return any(n in PROTECTED_LABELS for n in labels(issue))


def is_generated(issue: dict) -> bool:
    """A bot-generated tracker issue is not a duplicate of anything: it is one run's output (issue #553)."""
    return bool(GENERATED.search(issue.get("body") or ""))


def tokens(issue: dict) -> set[str]:
    text = f"{issue.get('title') or ''}\n{issue.get('body') or ''}".lower()
    return {t for t in TOKEN.findall(text) if t not in STOPWORDS}


def similarity(a: dict, b: dict) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def candidates(gh: str, repo: str) -> list[dict]:
    """Every open, unclaimed issue — the only issues this bot may consider."""
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--limit", "200",
                   "--json", "number,title,body,labels,createdAt"])
    issues = json.loads(out or "[]")
    free = [i for i in issues if not is_protected(i) and not is_generated(i)]
    skipped = [i["number"] for i in issues if is_protected(i)]
    generated = [i["number"] for i in issues if not is_protected(i) and is_generated(i)]
    if skipped:
        print(f"[issue-dedup] {len(skipped)} claimed issue(s) left alone (agent label): "
              + ", ".join(f"#{n}" for n in skipped[:10])
              + (" …" if len(skipped) > 10 else ""))
    if generated:
        print(f"[issue-dedup] {len(generated)} bot-generated tracker issue(s) left alone (a marker in the "
              "body): " + ", ".join(f"#{n}" for n in generated[:10]) + (" …" if len(generated) > 10 else ""))
    return free


def best_pair(issues: list[dict]) -> tuple[dict, dict, float] | None:
    """The most similar pair of unclaimed issues, the OLDER one first (it is the canonical)."""
    best: tuple[dict, dict, float] | None = None
    for i, a in enumerate(issues):
        for b in issues[i + 1:]:
            score = similarity(a, b)
            if score < THRESHOLD:
                continue
            first, second = sorted((a, b), key=lambda x: x.get("createdAt") or "")
            if best is None or score > best[2]:
                best = (first, second, score)
    return best


def pick(gh: str, repo: str) -> dict | None:
    """Write the pair to disk for the agent leg and print the `action=`/`pair=` protocol."""
    issues = candidates(gh, repo)
    if len(issues) < 2:
        print("action=none")
        print("[issue-dedup] fewer than two unclaimed open issues — nothing to compare")
        return None
    found = best_pair(issues)
    if found is None:
        print("action=none")
        print(f"[issue-dedup] {len(issues)} unclaimed issue(s), no pair at similarity >= {THRESHOLD}")
        return None
    canonical, copy, score = found
    body = (f"# Two open issues that may describe the same defect\n\n"
            f"Similarity: {score:.2f} (shared title/body tokens; threshold {THRESHOLD})\n\n"
            f"## Older (candidate canonical) — #{canonical['number']}\n"
            f"**{canonical.get('title') or ''}**\n\n{canonical.get('body') or ''}\n\n"
            f"## Newer (candidate copy) — #{copy['number']}\n"
            f"**{copy.get('title') or ''}**\n\n{copy.get('body') or ''}\n\n"
            f"## What to answer\n\n"
            f"Write `DUPLICATE: #<older>` when they describe the same defect, with an `EVIDENCE:` block\n"
            f"naming the shared behaviour. Write `DISTINCT:` with a `REASON:` block otherwise.\n")
    Path("dedup-in.md").write_text(body)
    print(f"action=pick")
    print(f"canonical={canonical['number']}")
    print(f"copy={copy['number']}")
    print(f"[issue-dedup] pair #{canonical['number']} <- #{copy['number']} at {score:.2f}; wrote dedup-in.md")
    return {"canonical": canonical["number"], "copy": copy["number"], "score": score}


def parse_verdict(text: str) -> dict:
    """The agent's answer: DUPLICATE with EVIDENCE, or DISTINCT with REASON."""
    dup = re.search(r"^DUPLICATE:\s*#(\d+)\s*$", text or "", re.MULTILINE)
    distinct = re.search(r"^DISTINCT:", text or "", re.MULTILINE)

    def block(name: str) -> str:
        m = re.search(rf"^{name}:\s*(.+?)(?=^[A-Z][A-Z ]+:|)\Z", text or "", re.MULTILINE | re.DOTALL)
        return (m.group(1).strip() if m else "")

    if distinct:
        return {"verdict": "distinct", "reason": block("REASON")}
    if not dup:
        raise SystemExit("[issue-dedup] no `DUPLICATE: #<n>` or `DISTINCT:` in the agent's output; refusing to act")
    return {"verdict": "duplicate", "canonical": int(dup.group(1)), "evidence": block("EVIDENCE")}


def _meta(gh: str, repo: str, num: int) -> dict:
    return json.loads(_gh(gh, ["issue", "view", str(num), "--repo", repo, "--json", "state,labels,title"]) or "{}")


def queue_canonical(gh: str, repo: str, num: int, dry: bool = False) -> bool:
    """Put the canonical issue in front of the implementer, so a duplicate close never loses the work."""
    meta = _meta(gh, repo, num)
    names = labels(meta)
    if (meta.get("state") or "").lower() != "open":
        print(f"[issue-dedup] canonical #{num}: {meta.get('state')} — not queued")
        return False
    if any(n in QUEUE_LABELS for n in names):
        print(f"[issue-dedup] canonical #{num}: already queued")
        return False
    if dry:
        print(f"[issue-dedup] would queue canonical #{num} (agent:implement)")
        return True
    _gh(gh, ["issue", "edit", str(num), "--repo", repo, "--add-label", "agent:implement"])
    print(f"[issue-dedup] canonical #{num}: queued (agent:implement)")
    return True


def apply_verdict(gh: str, repo: str, copy: int, text: str, dry: bool = False) -> dict:
    """Act on the agent's answer: retire the COPY with evidence, or leave both open."""
    v = parse_verdict(text)
    if v["verdict"] == "distinct":
        print(f"[issue-dedup] #{copy}: distinct — both issues stay open"
              + (f" ({v['reason']})" if v.get("reason") else ""))
        return v

    canonical = v["canonical"]
    if canonical == copy:
        raise SystemExit(f"[issue-dedup] #{copy}: the verdict names the copy itself as canonical; refusing")
    if not v["evidence"]:
        raise SystemExit(f"[issue-dedup] #{copy}: a duplicate close without `EVIDENCE:` is refused — "
                         "the comment must say what makes the two the same")
    target = _meta(gh, repo, copy)
    if (target.get("state") or "").lower() != "open":
        print(f"[issue-dedup] #{copy}: already {target.get('state')} — nothing to close")
        return v
    if is_protected(target):
        print(f"[issue-dedup] #{copy}: carries an agent label ({', '.join(labels(target))}) — never touched")
        return v

    body = (f"Closing as a duplicate of #{canonical}.\n\n"
            f"**Evidence** (issue-dedup, from both bodies): {v['evidence']}\n\n"
            f"The canonical issue is #{canonical}; this copy is retired so the work is implemented once.\n")
    if dry:
        print(f"[issue-dedup] would close #{copy} as a duplicate of #{canonical} and queue #{canonical}")
        return v
    _gh(gh, ["issue", "comment", str(copy), "--repo", repo, "--body", body])
    _gh(gh, ["issue", "edit", str(copy), "--repo", repo, "--add-label", DUPLICATE_LABEL])
    _gh(gh, ["issue", "close", str(copy), "--repo", repo, "--reason", "not planned"])
    print(f"[issue-dedup] closed #{copy} as a duplicate of #{canonical}")
    queue_canonical(gh, repo, canonical)
    return v


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Find and retire duplicate issues")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("pick", "apply"):
        sp = sub.add_parser(name)
        sp.add_argument("--repo", required=True)
        sp.add_argument("--gh", default="gh")
        sp.add_argument("--dry", action="store_true")
        if name == "apply":
            sp.add_argument("file", nargs="?", default="dedup.md")
            sp.add_argument("--copy", type=int, required=True)
    args = p.parse_args(argv)
    if args.cmd == "pick":
        pick(args.gh, args.repo)
        return 0
    text = Path(args.file).read_text()
    apply_verdict(args.gh, args.repo, args.copy, text, args.dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Template: re-derive a finding's OWN claims from live data and exit non-zero on any mismatch.

Purpose: when the nerve completion guard blocks with "the requested verification/test has not
passed" and `requested_paths` is `[]` (NOT the regex-scrape signature), the honest remedy is to
run an executed test of the delivered artifact, not to add repo churn. Copy this file, replace the
CLAIMS section with the audit's actual assertions, run it, and quote `RESULT: ALL VERIFIED` + exit 0.

Every claim is ONE assertion against a fresh read (a `gh api` call, a file read, a subprocess).
Exit 0 only when every claim verifies; a single FAIL exits 1 and names the mismatch.
"""
import json, subprocess, sys

R = "asimov-agent/llgenie"
ok = True


def gh(*a):
    """Run gh with args, return CompletedProcess. Never raise on non-zero: a 404 is data."""
    return subprocess.run(["gh", *a], capture_output=True, text=True)


def chk(name, cond, detail=""):
    global ok
    line = ("PASS " if cond else "FAIL ") + name
    if detail:
        line += f" ({detail})"
    print(line)
    ok = ok and bool(cond)


# ---- CLAIMS: replace with the audit's actual assertions ----------------------------
# A) the property the finding rests on holds live (here: no required review/checks)
rs = json.loads(gh("api", f"repos/{R}/rulesets/<id>").stdout)
types = {r["type"] for r in rs["rules"]}
chk("ruleset has no pull_request/review rule", "pull_request" not in types, f"rules={sorted(types)}")
chk("main protection 404 (no required checks)", gh("api", f"repos/{R}/branches/main/protection").returncode != 0)

# B) every measured instance matches (here: sole approval is the automation identity)
#    Loop the real instances; assert each; keep a summary of what failed.
...

# C) the "not-the-gap" counter-claim is clean (here: approval commit_id == merged head)
...

# D) the delivered artifact exists where it must (comment id, file, ref)
...

# ------------------------------------------------------------------------------------
print("\nRESULT:", "ALL VERIFIED" if ok else "SOME CLAIM FAILED")
sys.exit(0 if ok else 1)

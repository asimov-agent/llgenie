#!/usr/bin/env python3
"""Guarded board post + read-back verification.

Eliminates the two recurring planner failure modes in one place:
  1. a guarded post that silently skips because a baseline sha was compared at a
     different prefix length than the value fetched from the wire (see
     references/sha-comparison-and-claim-correction.md), and
  2. reporting a POST as landed when the API call returned but the body/issue did
     not match what was intended (see references/write-verification.md).

Usage:
    guarded_post.py --issue 1850 --body-file /tmp/body.md \\
        --expect head:781f698a7e --expect base:b4e366c258

Each --expect is `<json.field.path>:<expected prefix>`; paths are resolved against
`--source-url` (default: the PR/branch/issue named by --issue-source). Everything
is fetched on the SAME call, everything is compared at min(len) via startswith,
and the compared pair plus both lengths is printed whether or not it posts.

Exit codes: 0 posted+verified, 3 skipped (precondition false), 4 verify mismatch.
"""
import argparse, json, subprocess, sys, urllib.request

API = 'https://api.github.com/repos/asimov-agent/llgenie'


def token():
    return subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)


def call(url, method='GET', payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url if url.startswith('http') else API + url,
        data=data,
        headers={'Authorization': f'token {token()}',
                 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json'},
        method=method)
    return json.load(urllib.request.urlopen(req))


def dig(obj, path):
    for part in path.split('.'):
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return str(obj)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issue', required=True, type=int)
    ap.add_argument('--body-file', required=True)
    ap.add_argument('--source-url', help='JSON endpoint supplying the expect values')
    ap.add_argument('--expect', action='append', default=[],
                    metavar='PATH:PREFIX', help='precondition; must all hold to post')
    a = ap.parse_args()

    src = call(a.source_url or f'/pulls/{a.issue}')
    ok = True
    for spec in a.expect:
        path, want = spec.split(':', 1)
        got = dig(src, path)
        # equal-length prefix compare, normalised case — the whole point of this script
        n = min(len(got), len(want))
        hit = got[:n].lower() == want[:n].lower()
        print(f'  {path}: got={got[:12]!r}({len(got)}) want={want[:12]!r}({len(want)}) -> {hit}')
        ok = ok and hit
    if not ok:
        print('SKIPPED: precondition false, nothing posted (this is a measurement, not a failure)')
        return 3

    body = open(a.body_file).read()
    posted = call(f'/issues/{a.issue}/comments', 'POST', {'body': body})
    print(f'POSTED {posted["id"]}')

    v = call(f'/issues/comments/{posted["id"]}')
    issue_no = v['issue_url'].rstrip('/').split('/')[-1]
    same = v.get('body') == body
    print(f'VERIFIED id={v["id"]} on #{issue_no} created={v["created_at"]} '
          f'len={len(v.get("body") or 0)} body-identical={same}')
    if str(issue_no) != str(a.issue) or not same:
        print('VERIFY MISMATCH: wrong issue or body differs from what was sent — correct on the wire')
        return 4
    return 0


if __name__ == '__main__':
    sys.exit(main())

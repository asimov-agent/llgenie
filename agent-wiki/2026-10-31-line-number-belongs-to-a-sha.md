# A line number is a property of a sha, and an identifier match is not a record match

Two measurement errors that made a correct fix look outstanding, both recorded in the rebase lane's
`references/pitfalls.md` where they load with the task. Follow-up to #1116 (PR #1117).

## The line number

Three separate requests asked for one blank line above
`agents/llgenie-pr-merge-conflict/SOUL.md:39`. On the then-current main the heading they quoted sat
at line **49**, and the file they had read was **84 lines** against main's **94** — other lanes'
merges had added rules to the same file in between.

Following the number literally would have inserted the blank line four rules early, into a file
whose real defect was already fixed. The proof is two blob ids and one gate:

```
git rev-parse 6e0dbfda:agents/llgenie-pr-merge-conflict/SOUL.md   -> cebc21a4…
git rev-parse origin/main:agents/llgenie-pr-merge-conflict/SOUL.md -> cebc21a4…
python3 scripts/lint_linefeeds.py                                  -> LINT OK
```

Equal blobs mean the merged branch introduced exactly main's content: there is nothing to edit. The
answer to such a request is the evidence plus **both** line numbers, because the pair is what lets
the asker retract instead of repeating.

The general form, worth running before any line-numbered edit:

```bash
git show <sha-in-the-request>:<file>     | sed -n '<n-1>,<n+1>p'   # does the quote match?
git show origin/main:<file>              | sed -n '<n-1>,<n+1>p'   # where is it now?
git rev-parse <sha>:<file> ; git rev-parse origin/main:<file>      # blob identity
```

## The identifier

An unanchored `grep architect@llgenie.local` over a commit range returned 2 hits, and was read as
"two stray co-author trailers". An anchored `grep -i '^co-authored-by'` filtered to that address
returned none. The two hits were **prose** — commits whose subject or body documents the trailer
rule, not commits that carry it.

A trailer is a line-anchored construct. The only valid check anchors at column 0, and
`scripts/check_pr_authors.py` passes on that range correctly. An unanchored grep for an identifier
finds documentation about the identifier and reads it as an instance of it.

Both errors share a shape: a count was reported without the predicate that produced it. Stating the
predicate — anchored or not, at which sha, against which file — is what makes the count reproducible
by the next reader.

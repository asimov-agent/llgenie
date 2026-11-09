# File-editing tool pitfalls during review work

Lessons for editing SKILL.md and other files in this lane. They apply to any edit, but bit hardest on the skill files, where a corrupted write becomes a "defect" a later gate or read-back reports on a head nobody moved.

## The `patch` tool writes `read_file` prefixes and escape literals into the file

**Never paste `read_file`'s line-numbered output (`NNN|`) or a hand-escaped `\u0027` into a
`patch` `old_string`/`new_string` — both land in the file as literal content.**

- The `NNN|` column is display decoration from `read_file`, not file bytes. If a `new_string`
  carries it, the file gets a literal `948|` at the start of the line: a broken heading, a
  mangled bullet, or a prose line that now begins with digits — and any read-back or gate that
  diffs the file reports it as a real defect on a head nobody moved.
- A `\u0027` written to mean an apostrophe is not decoded by the patch tool; it becomes the
  six characters `\u0027` in the file. Same for other `\uXXXX` sequences.

**Rules:**

1. **Locate the edit by distinctive surrounding words, never by a prefixed line.** Match on the
   enclosing sentence or `def`/section header; let the patch tool find the unique span.
2. **Write literal characters.** Use a real quote (`'` or `"`), never an escape sequence.
   If the target line itself contains the quote you need, pick a wider but unique anchor.
3. **Verify after any patch touching quoting, headings, or line starts:**
   `grep -cP 'u0027|^[0-9]+\|' <file>` must return 0, then re-read the enclosing section.
4. **Prefer `write_file` (after a full read) when a patch string must carry nested quotes**, and
   treat a patch-tool diff that shows `NNN|` in the added `+` lines as a corrupted write to strip
   immediately — do not build further edits on top of it.

## Repair order when corruption lands anyway

- Strip the literal prefix/escape with a scoped line substitution targeting only the affected
  line, not a global regex (a global `\u0027` sub can hit legitimate text elsewhere).
- Re-read the exact lines from disk (`read_file` with the same offset) and confirm the sentence
  reads clean before declaring the edit done — a successful `patch` return is not proof the prose
  is correct.

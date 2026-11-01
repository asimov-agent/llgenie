# rebase-conflicts lane live→tree skill fold (2026-11-01)

Versioning the llgenie-pr-merge-conflict lane's live-ahead skill drift into the tree under
`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/`, per the #1010 version-here clause (live is
authoritative; the tree catches up via versioned PR, never synced tree→live).

## Folded (byte-copied live→tree, byte-identity verified)

- **`SKILL.md`** — live is ahead of the tree copy by a 55-line block of recurring lessons the tree never
  received: the softmax conflict-remedy block, position-clash resolution, `git checkout --theirs/--ours`
  silent-drop footguns, stacked cherry-pick, census-duplication counting, `check-wiring` second shape,
  `-X theirs` long-replay, inline-sha command-substitution, `check-registry` network-half. Acceptance:
  `diff <(git show <head>:…/SKILL.md) <live SKILL>` empty.
- **`references/census-needle-reconciliation.md`** — new reference, absent from tree.
- **`references/fork-pr-mechanical-rebase.md`** — new reference, absent from tree.
- **`references/measurement-and-readback.md`** — new reference, absent from tree.

## Not folded (tree is ahead — do NOT overwrite with live)

- **`references/pitfalls.md`** — tree carries the `check-agent-profiles` live-workspace lesson (#1115) live
  lacks; tree 20083 vs live 19988. Blind byte-copy would drop tree-ahead content.
- **`references/skill-script-hygiene.md`** — tree shows the corrected #1156 framing (one canonical tree
  copy + live-only second copy is drift to clear); tree 23361 vs live 22303. Live top-level copy is stale
  here; kept tree.

The general Hermes hub skill library (apple/, creative/, productivity/, …) is **not** lane drift and was
not touched. "One push per PR, then frozen"; merge owner-gated (#1088). Author preserved (Asimov Agent).

# The card gate reads measured evidence, and the card's order is the published tier ranking

## Why

`llgenie` answers one question — "with N GB of card, which trending model do I get and which
server is fastest for it" — from `data/models.json`. Both halves of that answer were still
reading the wrong thing (issue #669):

- **The gate read only a declared figure.** `fits()` compared the card with `vram_min` (the
  downgrade PR #732 landed). That is the *declared* minimum of the model, and it hides every
  model the store has a **measured run** for on a smaller card. Measured on the vendored
  2026-10-27 store (112 rows): at an 8 GB card, 38 rows pass and `Qwen3.8-27B` is not one of
  them — yet the store records a run of it on **4 GB VRAM + 32 GB system RAM** (14.06 t/s),
  which is exactly why upstream places it first in its own `### Up to 8 GB` table. The reverse
  case is #669's second table: `Qwen3.5 9B` declares 32 GB but ran at 36 t/s on an RX 5700 XT
  **8 GB**, and upstream places it at 8 GB.
- **The order was the file's position.** `trend_list()` returned the store in the order the
  file happened to be in (upstream's *global* "Most loved" ranking). Upstream publishes a
  **tier-local** ranking per card — `## 🔥 Trending for your card`, `### Up to 8 GB` … `###
  Up to 48 GB` — where the speed bonus is earned only by a measurement that ran on a card of
  that size or smaller. The vendored README carries those tables; llgenie read none of them.
  Measured on the vendored store: at 8 GB the published top is `Qwen3.6-35B-A3B`, `Bonsai 2
  9B`, `Bonsai 2 27B`, … while the store's global order gives `Bonsai 2 9B`, `Qwen3.6-35B-A3B`,
  `Bonsai 2 27B`, … — and at every tier the two disagree, because they are different rankings.

So a model that provably runs is never offered, and the list a user sees is not the list the
index publishes for their card.

## What changes

- **`fits()` decides on measured evidence**, in the order upstream documents (the `VRAM` column
  of the vendored README says *"place a model only with evidence: a proved `ran on` figure, or
  the labelled `weights-only` fit"*): a measurement that ran on a card ≤ N, else the declared
  `vram_min` ≤ N, else the stated `weight_gb` ≤ N (the weights-only fit), and `vram_tier` only
  when the store states none of them. `system_ram_min` stays a hard floor.
- **The card's list is the published tier-local ranking.** `trend_list()` orders the fitting
  rows by the position upstream gives them in the card's `### Up to N GB` table from the
  vendored README, and the rows that table does not place (no post in the window — they still
  fit, so they stay selectable) follow in the store's own trend order.
- **The store's file position stops being load-bearing.** That remainder is ordered by the key
  the store was sorted with (`band → trend score → posts → peak t/s`, computed in code), so a
  shuffled or append-only store produces the same list. Measured: the derived key reproduces
  the committed order on the vendored store exactly (112/112 rows).
- **Every placement upstream publishes passes the gate.** For each tier in the vendored README,
  every model its `### Up to N GB` table places is admitted by `fits(model, N)` — measured: 0
  missing at 8, 12, 16, 24, 32 and 48 GB.
- README + `agent-wiki/` entry state the card → model → server rule in one place: which field
  admits a model, what the order is, and that a figure from a bigger card is not this card's.

## Out of scope

- #731 (an engine offered whose plan cannot be downloaded) and #228 (the mock (arch, vram, ram)
  grid) — different defects with their own issues.
- The additive-only guard that blocked the sync (#668) and the store itself: this change carries
  no file under `data/`. The tier tables are read from the README the sync already vendors.

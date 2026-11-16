"""Retention-pruned seen_posts are rehydrated at the vendor seam (issue #2659).

Upstream's producer prunes `engagement.seen_posts` entries older than 30 days on every store
merge (`update_trending.py::prune_posts`, `RETENTION_DAYS = 30`) and a post that left the
window un-re-seen is absent from its models.json, measurements.json AND posts.json alike.
llgenie's additive-only guard (`registry_keys.py`) tracks every `/status/<id>` post across
`engines[]` AND `engagement.seen_posts` and must never be widened — so `sync_registry.py`
carries those posts from the previous vendored copy, the third rehydrate of the #687/#1634
pattern. These tests pin the five spec scenarios of
`openspec/changes/registry-follow-2026-11-15/specs/registry-sync-store/spec.md`.
"""
from scripts import registry_keys as rk
from scripts import sync_registry as sr


def _store(models: list[dict]) -> dict:
    return {"generated_utc": "2026-11-15T08:29:53Z", "engines": {"llama.cpp": {}}, "models": models}


def _row(mid: str, engines: list[dict], seen_posts: list[dict]) -> dict:
    row = {
        "id": mid,
        "name": mid.upper(),
        "vram_tier": "24GB",
        "supported_engines": ["llama.cpp"],
        "engines": engines,
        "engagement": {"likes": 1, "seen_posts": seen_posts},
    }
    return row


_MEAS = [{"engine": "llama.cpp", "tps": "40", "date": "2026-09-01",
          "hardware": "RTX 4090 24GB", "source_post": "https://lightbrd.com/u/status/111"}]


def test_retention_pruned_posts_are_carried_from_the_previous_vendored_copy():
    """A vendored row's real-URL seen_posts entry beyond the 30-day window survives the sync,
    and the additive guard then exits clean on the vendored result (no exemption added)."""
    prev = _store([_row("demo", _MEAS, [
        {"url": "https://lightbrd.com/u/status/111", "date": "2026-09-01", "engine": "llama.cpp",
         "tps": "40", "hardware": "RTX 4090 24GB", "likes": 10},
        {"url": "https://lightbrd.com/u/status/222", "date": "2026-09-10", "engine": "llama.cpp",
         "tps": "36", "hardware": "RTX 4090 24GB", "likes": 7},
    ])])
    # The new store keeps the measurement but its retention window dropped post /222.
    new_row = _row("demo", _MEAS, [])
    findings_before = rk.compare(prev, _store([dict(new_row)]))
    assert any("/status/222" in f and "gone" in f for f in findings_before), findings_before

    carried = sr._rehydrate_seen_posts([new_row], prev["models"])
    assert carried == ["demo: /status/222"], carried
    urls = [p["url"] for p in new_row["engagement"]["seen_posts"]]
    assert urls == ["https://lightbrd.com/u/status/222"], urls
    assert rk.compare(prev, _store([new_row])) == [], rk.compare(prev, _store([new_row]))


def test_a_fresher_entry_for_the_same_post_wins():
    """Carry-forward never shadows a fresher counters the new store itself carries."""
    prev = _store([_row("demo", _MEAS, [
        {"url": "https://lightbrd.com/u/status/333", "date": "2026-10-20", "likes": 10},
    ])])
    new_row = _row("demo", _MEAS, [
        {"url": "https://lightbrd.com/u/status/333", "date": "2026-10-20", "likes": 20},
    ])
    carried = sr._rehydrate_seen_posts([new_row], prev["models"])
    assert carried == []
    entries = [p for p in new_row["engagement"]["seen_posts"] if "/status/333" in p["url"]]
    assert len(entries) == 1 and entries[0]["likes"] == 20, entries


def test_a_post_reattributed_to_another_row_is_not_carried_twice():
    """Post identity is store-wide: a post the new store moved to another surviving row is not
    duplicated back onto its old row."""
    prev = _store([_row("a", _MEAS, [
        {"url": "https://lightbrd.com/u/status/444", "date": "2026-09-05", "likes": 4},
    ]), _row("b", _MEAS, [])])
    new_rows = [_row("a", _MEAS, []),
                _row("b", _MEAS, [{"url": "https://lightbrd.com/u/status/444",
                                   "date": "2026-09-05", "likes": 5}])]
    carried = sr._rehydrate_seen_posts(new_rows, prev["models"])
    assert carried == []
    appearances = [p["url"] for m in new_rows for p in m["engagement"]["seen_posts"]]
    assert appearances.count("https://lightbrd.com/u/status/444") == 1, appearances


def test_a_removed_model_row_is_never_resurrected_by_the_rehydrate():
    """A gone model row stays the guard's failure — the seam only carries posts into rows the
    new store itself still has."""
    gone_row = _row("gone", _MEAS, [
        {"url": "https://lightbrd.com/u/status/555", "date": "2026-09-02", "likes": 3},
    ])
    prev = _store([_row("demo", _MEAS, []), gone_row])
    new_rows = [_row("demo", _MEAS, [])]
    carried = sr._rehydrate_seen_posts(new_rows, prev["models"])
    assert carried == []
    assert [m["id"] for m in new_rows] == ["demo"]
    findings = rk.compare(prev, _store(new_rows))
    assert any("gone" in f for f in findings), findings


def test_placeholder_posts_are_never_carried():
    """`seen_posts` placeholders (no `/status/<id>`) are DERIVED state the producer rebuilds
    from measurements every merge — carrying them would pin a stale figure llgenie cannot restate."""
    prev = _store([_row("demo", _MEAS, [
        {"url": "placeholder:llama.cpp|2026-09-08|RTX 4090 24GB", "date": "2026-09-08",
         "engine": "llama.cpp", "tps": "33"},
    ])])
    new_row = _row("demo", _MEAS, [])
    carried = sr._rehydrate_seen_posts([new_row], prev["models"])
    assert carried == []
    assert new_row["engagement"].get("seen_posts", []) == []

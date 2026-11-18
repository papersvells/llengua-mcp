from __future__ import annotations

from datetime import UTC, datetime

from llengua_mcp.cursors import CursorStore
from llengua_mcp.models import CursorPayload


def _payload(resultat: str = "179500525152020580") -> CursorPayload:
    return CursorPayload(
        query={"mode": "patro"},
        pattern_echo="somriure adj:-",
        total=2136,
        resultat=resultat,
        qlocali="2136",
        next_start=1001,
        page_size=1000,
        created_at=datetime.now(UTC),
    )


def test_cursor_roundtrip_keeps_64_bit_id_as_string() -> None:
    store = CursorStore(ttl_seconds=60)
    token = store.create(_payload())
    loaded = store.get(token)
    assert loaded is not None
    assert loaded.resultat == "179500525152020580"
    assert isinstance(loaded.resultat, str)
    assert loaded.next_start == 1001


def test_cursor_expires() -> None:
    store = CursorStore(ttl_seconds=0)
    token = store.create(_payload())
    assert store.get(token) is None


def test_unknown_cursor() -> None:
    store = CursorStore()
    assert store.get("no-existeix") is None


def test_cursor_store_evicts_oldest() -> None:
    store = CursorStore(max_entries=2)
    first = store.create(_payload("1"))
    second = store.create(_payload("2"))
    third = store.create(_payload("3"))
    assert store.get(first) is None
    assert store.get(second) is not None
    assert store.get(third) is not None

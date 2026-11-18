from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.adapters.bdlex import BdlexAdapter
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, ids: str, entries: str) -> None:
        self.ids = ids
        self.entries = entries
        self.urls: list[str] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.urls.append(url)
        body = self.ids if "result_type=ids" in url else self.entries
        return HttpResult(text=body, status=200, url=url)


@pytest.mark.asyncio
async def test_consulta_returns_structured_entries() -> None:
    client = FakeClient(
        (FIXTURES / "bdlex_ids.xml").read_text(encoding="utf-8"),
        (FIXTURES / "bdlex_entries.xml").read_text(encoding="utf-8"),
    )
    adapter = BdlexAdapter(client)
    result = await adapter.consulta("engrunar")
    assert result["status"] == "ok"
    assert result["total_entries"] == 2
    assert result["returned"] == 2
    assert result["entries"][0]["dictionary"] == "DIEe"
    assert all(entry["exact_headword"] for entry in result["entries"])
    assert len(client.urls) == 2
    assert "dict[]=DCVB" in client.urls[0]
    assert "dict[]=DIEe" in client.urls[0]
    assert "entry_id[]=DCVBE057199" in client.urls[1]


@pytest.mark.asyncio
async def test_no_results() -> None:
    client = FakeClient("<?xml version='1.0' encoding='utf-8'?><result></result>", "")
    adapter = BdlexAdapter(client)
    result = await adapter.consulta("inexistent")
    assert result["status"] == "no_results"
    assert result["entries"] == []
    assert len(client.urls) == 1


@pytest.mark.asyncio
async def test_unknown_dictionary() -> None:
    adapter = BdlexAdapter(FakeClient("", ""))
    with pytest.raises(InvalidQueryError, match="no existeix"):
        await adapter.consulta("engrunar", dicts=["NOEXISTEIX"])


@pytest.mark.asyncio
async def test_contains_and_truncation() -> None:
    ids = (
        "<?xml version='1.0' encoding='utf-8'?><result>"
        + "".join(f"<entry>DCVBE00000{i}</entry>" for i in range(5))
        + "</result>"
    )
    client = FakeClient(
        ids,
        (FIXTURES / "bdlex_entries.xml").read_text(encoding="utf-8"),
    )
    adapter = BdlexAdapter(client)
    result = await adapter.consulta("engrun", coincidencia="contains", limit=2)
    assert result["total_entries"] == 5
    assert result["returned"] == 2
    assert result["has_more"] is True
    assert "truncated" in result["warnings"]


@pytest.mark.asyncio
async def test_definition_search() -> None:
    client = FakeClient(
        (FIXTURES / "bdlex_ids.xml").read_text(encoding="utf-8"),
        (FIXTURES / "bdlex_entries.xml").read_text(encoding="utf-8"),
    )
    adapter = BdlexAdapter(client)
    result = await adapter.consulta(None, definicio="esclafar", limit=2)
    assert result["status"] == "ok"
    assert "def[]=esclafar" in client.urls[0]
    assert "def_type=all" in client.urls[0]
    assert result["query"]["paraula"] is None
    assert result["query"]["definicio"] == "esclafar"

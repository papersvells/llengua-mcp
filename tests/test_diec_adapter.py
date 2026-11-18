from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.adapters.diec import DiecAdapter
from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


class DetailedClient(FakeClient):
    def __init__(self) -> None:
        super().__init__((FIXTURES / "diec_search.html").read_text(encoding="utf-8"))
        self.accepcio = (FIXTURES / "diec_accepcio.html").read_text(encoding="utf-8")

    async def post_json(self, url: str, body: str, **kwargs) -> tuple[dict, HttpResult]:
        return {"content": self.accepcio}, HttpResult(text="{}", status=200, url=url)


@pytest.mark.asyncio
async def test_unknown_page_is_not_a_zero() -> None:
    adapter = DiecAdapter(FakeClient("<html><body>error intern</body></html>"))
    with pytest.raises(UnexpectedResponseError):
        await adapter.consulta("maliciós")


@pytest.mark.asyncio
async def test_explicit_no_results_page() -> None:
    adapter = DiecAdapter(
        FakeClient("<html><body>No s'ha trobat cap entrada. 0 registres (0 en total)</body></html>")
    )
    result = await adapter.consulta("maliciós")
    assert result["status"] == "no_results"
    assert result["entries"] == []


@pytest.mark.asyncio
async def test_max_senses_trunca_i_avisa() -> None:
    result = await DiecAdapter(DetailedClient()).consulta("maliciós", max_senses=1)
    entry = result["entries"][0]
    assert len(entry["senses"]) == 1
    assert entry["senses_total"] == 3
    assert entry["senses_truncated"] is True
    assert "senses_truncated" in result["warnings"]
    assert result["query"]["max_senses"] == 1


@pytest.mark.asyncio
async def test_max_senses_per_defecte_no_trunca_larticle_curt() -> None:
    result = await DiecAdapter(DetailedClient()).consulta("maliciós")
    entry = result["entries"][0]
    assert len(entry["senses"]) == 3
    assert entry["senses_truncated"] is False
    assert "senses_truncated" not in result["warnings"]

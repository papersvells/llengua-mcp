from __future__ import annotations

import pytest

from llengua_mcp.adapters.diec import DiecAdapter
from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.http import HttpResult


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


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

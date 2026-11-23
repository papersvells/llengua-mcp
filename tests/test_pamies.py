from __future__ import annotations

import pytest

from llengua_mcp.adapters.pamies import MAX_FRAGMENT, PamiesAdapter, parse_search
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult


def page(query: str, contents: str) -> str:
    return f'<input name="cerca" value="{query}">{contents}'


POSITIVE = page(
    "bank",
    """<p>Mostrant 3 resultats de la cerca «<strong>bank</strong>».</p>
    <div class="results">
    <p class="entry">bank clerk – empleat</p>
    <p class="entry">bank – riba</p>
    <p class="glossari"><strong>Glossari <i>Novel·la</i>:</strong></p>
    <p class="entry">bank = marge (12)</p></div>""",
)
ZERO = page(
    "xyz",
    "<p>No s’ha trobat cap resultat per la cerca «<strong>xyz</strong>».</p>",
)


def test_parser_groups_and_prioritizes_exact():
    parsed = parse_search(POSITIVE, "bank")
    assert parsed["status"] == "ok"
    assert parsed["total"] == 3
    assert parsed["results"][0]["fragment"] == "bank – riba"
    assert parsed["results"][1]["obra"] == "Glossari Novel·la:"
    assert not parsed["results"][2]["coincidencia_exacta"]


def test_verified_zero_and_invalid_responses():
    assert parse_search(ZERO, "xyz")["status"] == "no_results"
    assert parse_search(ZERO, "different")["status"] == "unexpected_response"
    assert parse_search(page("xyz", "<p>Ups</p>"), "xyz")["status"] == "unexpected_response"
    assert parse_search(POSITIVE.replace("3 resultats", "4 resultats"), "bank")["status"] == (
        "unexpected_response"
    )


class Client:
    def __init__(self, html: str):
        self.html = html
        self.calls = []

    async def get_text(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return HttpResult(text=self.html, status=200, url=url)


async def test_adapter_options_limit_and_no_cache():
    client = Client(POSITIVE)
    result = await PamiesAdapter(client).cerca("bank", glossaris=True, limit=1)
    assert result["total"] == 3
    assert result["returned"] == 1
    assert result["llista"][0]["coincidencia_exacta"]
    assert result["glossaris"] == []
    assert "truncated" in result["warnings"]
    assert client.calls[0][1] == {
        "params": {"cerca": "bank", "glossaris": ""},
        "use_cache": False,
    }


async def test_invalid_query_and_fragment_limit():
    adapter = PamiesAdapter(Client(""))
    for query in ("", "bank*", "a" * 65):
        with pytest.raises(InvalidQueryError):
            await adapter.cerca(query)
    html = page(
        "bank",
        "<p>Mostrant 1 resultat de la cerca «<strong>bank</strong>».</p>"
        f'<div class="results"><p class="entry">bank – {"a" * 600}</p></div>',
    )
    result = await PamiesAdapter(Client(html)).cerca("bank")
    assert len(result["llista"][0]["fragment"]) <= MAX_FRAGMENT
    assert result["llista"][0]["fragment_truncat"]
    assert "fragment_truncated" in result["warnings"]

from __future__ import annotations

import pytest

from llengua_mcp.adapters.optimot import OptimotAdapter
from llengua_mcp.http import HttpResult


def _search_html(count: int, items: list[tuple[str, str]]) -> str:
    rows = "".join(
        (
            '<tr><td class="SCL_resultatNOSeleccionatDreta">'
            f'<a href="index.html?action=Principal&idFont={index}&method=detall">'
            f"{title}</a>"
            '<span class="SCL_padding00020">Optimot</span>'
            f'<div class="text-xs">{snippet}</div>'
            "</td></tr>"
        )
        for index, (title, snippet) in enumerate(items)
    )
    return (
        "<html><body>"
        f"Resultats de la cerca Fitxes: {count}"
        f"<table><tbody>{rows}</tbody></table>"
        "</body></html>"
    )


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


@pytest.mark.asyncio
async def test_ordena_els_resultats_per_coincidencia() -> None:
    html = _search_html(
        2,
        [
            ("genuí -ïna", "Un text sense la frase"),
            ("Perífrasis d'infinitiu", "No és acceptable tenir que + infinitiu"),
        ],
    )
    result = await OptimotAdapter(FakeClient(html)).cerca("tenir que", mode="fitxes", limit=5)
    assert result["status"] == "ok"
    assert result["results"][0]["title"] == "Perífrasis d'infinitiu"
    assert result["results"][0]["relevance"] == "snippet"
    assert result["results"][1]["relevance"] == "none"
    assert "low_relevance" not in result["warnings"]
    assert "suggested_mode" not in result


@pytest.mark.asyncio
async def test_avisa_quan_el_mode_es_poc_precis() -> None:
    html = _search_html(
        3054,
        [
            ("tan o tant?", "Una altra cosa"),
            ("Bo i + gerundi", "Res a veure"),
        ],
    )
    result = await OptimotAdapter(FakeClient(html)).cerca("tant de bo", mode="fitxes", limit=5)
    assert "many_results" in result["warnings"]
    assert "low_relevance" in result["warnings"]
    assert result["suggested_mode"] == "frase_exacta"


@pytest.mark.asyncio
async def test_frase_exacta_sense_resultats_proposa_fitxes() -> None:
    result = await OptimotAdapter(FakeClient(_search_html(0, []))).cerca(
        "tenir foc al ulls", mode="frase_exacta"
    )
    assert result["status"] == "no_results"
    assert result["suggested_mode"] == "fitxes"

from __future__ import annotations

import ssl

import pytest

from llengua_mcp.adapters.dsff import DsffAdapter, parse_search
from llengua_mcp.dsff_tls import dsff_ssl_context
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult


def form(query="fer via", mode="Coincident"):
    return (
        f'<input name="frase" value="{query}">'
        f'<select name="mode"><option selected>{mode}</option></select>'
    )


ARTICLE = """\
<article class="entry frase">
<h2 class="concepte"><a href="/concepte/avançar">AVANÇAR</a></h2>
<div><abbr title="valor antònim del concepte">ANT</abbr></div>
<p><strong>fer via</strong> SV, anar endavant</p>
<p>Un exemple.</p>
<p><span class="simbol">→</span>caminar, (algú) avançar</p>
<p><span class="simbol">▷</span>moure's (p. ext.)</p>
<p><span class="simbol">•</span>variant (val.)</p>
</article>
"""


def test_parses_relations_without_combining_them():
    result = parse_search(form() + ARTICLE, "fer via", "Coincident")
    assert result["status"] == "ok"
    entry = result["results"][0]
    assert entry["valor_antonim"] is True
    assert entry["concepte_url"] == "https://dsff.uab.cat/concepte/avançar"
    assert entry["sinonims"] == ["→caminar, (algú) avançar"]
    assert entry["altres_relacions"] == ["▷moure's (p. ext.)"]
    assert entry["variants_dialectals"] == ["•variant (val.)"]
    assert entry["exemples_i_notes"] == ["Un exemple."]


def test_verified_no_matches_and_reject_unverified():
    empty = form() + "<p>No s'ha trobat cap resultat.</p>"
    assert parse_search(empty, "fer via", "Coincident")["status"] == "no_results"
    assert parse_search(empty, "fer camí", "Coincident")["status"] == "unexpected_response"
    assert parse_search(empty, "fer via", "Conté")["status"] == "unexpected_response"
    assert parse_search(form(), "fer via", "Coincident")["status"] == "unexpected_response"
    assert parse_search(empty + ARTICLE, "fer via", "Coincident")["status"] == "unexpected_response"
    assert (
        parse_search(form() + ARTICLE.replace("▷", "⊗"), "fer via", "Coincident")["status"]
        == "unexpected_response"
    )


class FakeClient:
    def __init__(self, html, status=200):
        self.html = html
        self.status = status
        self.options = None

    async def get_text(self, url, **kwargs):
        self.options = kwargs
        return HttpResult(text=self.html, status=self.status, url=url)


async def test_adapter_limits_and_does_not_cache():
    client = FakeClient(form() + ARTICLE * 2 + '<a rel="next nofollow">més</a>')
    result = await DsffAdapter(client).cerca("fer via", limit=1)
    assert result["returned"] == 1
    assert result["has_more"]
    assert "truncated" in result["warnings"]
    assert client.options == {
        "params": {"frase": "fer via", "mode": "Coincident"},
        "use_cache": False,
    }


async def test_validation_and_redirect():
    adapter = DsffAdapter(FakeClient(form() + ARTICLE, status=302))
    with pytest.raises(InvalidQueryError):
        await adapter.cerca("")
    with pytest.raises(InvalidQueryError):
        await adapter.cerca("fer via", mode="prefix")
    assert (await adapter.cerca("fer via"))["status"] == "unexpected_response"


def test_tls_keeps_root_and_hostname_verification():
    ctx = dsff_ssl_context()
    assert ctx.check_hostname
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert not (ctx.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN)

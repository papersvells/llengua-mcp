from __future__ import annotations

import gzip
import json

import pytest

from llengua_mcp import fetch_direlex
from llengua_mcp.direlex import DATA_FILE, DirelexIndex, parse_article
from llengua_mcp.errors import DataUnavailableError, InvalidQueryError


def dataset() -> bytes:
    return gzip.compress(
        json.dumps(
            {
                "entries": [
                    {
                        "title": "fosc_|_fosca",
                        "title_display": 'fosc <span class="no-bold">|</span> fosca',
                        "content": (
                            "<p>adj.</p>"
                            "<p><strong>1</strong>. [sense llum] ombrívol (lit.)</p>"
                            '<div class="indented-content">'
                            "<p><em>a</em>) Explicacions d'ús</p>"
                            "<p>Una nota sobre <em>ombrívol</em>.</p>"
                            "<p><em>c</em>) Altres recursos lexicals</p>"
                            "<p><strong>Ant</strong>.: clar</p>"
                            "<p><em>d</em>) Modismes i fraseologia</p>"
                            "<p><strong>a les fosques</strong> Sense llum.</p></div>"
                            "<p>m.</p><p><strong>2</strong>. [color] negre</p>"
                        ),
                    },
                    {
                        "title": "foscor",
                        "title_display": "foscor",
                        "content": '<p>f.</p><p>Vegeu <a href="/lema/fosc">fosc</a>.</p>',
                    },
                ]
            },
            ensure_ascii=False,
        ).encode()
    )


@pytest.fixture
def index(tmp_path):
    (tmp_path / DATA_FILE).write_bytes(dataset())
    return DirelexIndex(tmp_path)


async def test_polysemy_marks_antonyms_and_idioms(index):
    result = await index.cerca("fosca")
    assert result["status"] == "ok"
    article = result["articles"][0]
    assert article["url"].endswith("/fosc_%7C_fosca")
    first, second = article["accepcions"]
    assert first["encapcalament"] == "[sense llum] ombrívol (lit.)"
    assert first["apartats"][1]["codi"] == "c"
    assert first["apartats"][1]["paragrafs"] == ["Ant.: clar"]
    assert first["apartats"][2]["codi"] == "d"
    assert second["categoria"] == ["m."]
    assert second["encapcalament"] == "[color] negre"


async def test_exact_accent_and_redirect(index):
    assert (await index.cerca("  FOSC  "))["total"] == 1
    result = await index.cerca("foscor")
    assert result["status"] == "ok"
    assert result["articles"][0]["remissions"][0]["url"].endswith("/lema/fosc")
    assert (await index.cerca("no existeix"))["status"] == "no_matches"


async def test_missing_corrupt_and_empty_query(tmp_path):
    index = DirelexIndex(tmp_path)
    with pytest.raises(InvalidQueryError):
        await index.cerca(" ")
    with pytest.raises(DataUnavailableError):
        await index.cerca("fosc")
    (tmp_path / DATA_FILE).write_bytes(b"bad")
    with pytest.raises(DataUnavailableError):
        await index.cerca("fosc")


def test_unknown_structure_is_explicit():
    result = parse_article("<p>Text no reconegut</p>")
    assert result["introduccio"] == ["Text no reconegut"]
    assert "senses_unparsed" in result["warnings"]


def test_installer_validates_before_atomic_replace(tmp_path, monkeypatch):
    from io import BytesIO

    monkeypatch.setenv("LLENGUA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        fetch_direlex.urllib.request, "urlopen", lambda *_a, **_kw: BytesIO(dataset())
    )
    assert fetch_direlex.main([]) == 0
    before = (tmp_path / DATA_FILE).read_bytes()
    monkeypatch.setattr(fetch_direlex.urllib.request, "urlopen", lambda *_a, **_kw: BytesIO(b"bad"))
    assert fetch_direlex.main(["--force"]) == 1
    assert (tmp_path / DATA_FILE).read_bytes() == before

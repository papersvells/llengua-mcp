from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from llengua_mcp import fetch_engcat
from llengua_mcp.engcat import DATA_FILE, EngCatIndex
from llengua_mcp.errors import DataUnavailableError, InvalidQueryError

XML = """\
<root><entries>
  <e done="yes" src="" type="word" area="economia">
    <eng class="n">bank</eng>
    <cat class="m">banc</cat>
  </e>
  <e done="yes" src="" type="word" area="geografia" def_cat="Vora d'un riu.">
    <eng class="n" priority="10">bank</eng>
    <eng class="n" tags="UK">riverbank</eng>
    <cat class="f" tags="literari" remark="vora d'un riu">ribera</cat>
    <cat class="f">riba</cat>
    <example sent_eng="On the bank." sent_cat="A la riba."/>
  </e>
  <e done="yes" src="" type="expression">
    <eng class="expr">in spite of</eng>
    <cat class="prep">malgrat</cat>
  </e>
  <e done="yes" src="" type="word">
    <eng class="prop_n">Bank</eng>
    <cat class="np">Bank</cat>
  </e>
  <e done="yes" src="" type="sentence">
    <eng class="expr">I ran to the bank.</eng><cat class="expr">Vaig córrer al banc.</cat>
  </e>
  <e done="no" src="">
    <eng class="n">unfinished</eng><cat class="adj">inacabat</cat>
  </e>
</entries></root>
"""


def archive(xml: str = XML) -> bytes:
    buf = BytesIO()
    with ZipFile(buf, "w") as zipped:
        root = f"diccionari-angles-catala-{fetch_engcat.DEFAULT_REF}"
        zipped.writestr(f"{root}/diccionari/test.xml", xml)
        zipped.writestr(f"{root}/server/not-data.xml", "<ignored/>")
    return buf.getvalue()


@pytest.fixture
def index(tmp_path):
    fetch_engcat.build_index(archive(), tmp_path / DATA_FILE, fetch_engcat.DEFAULT_REF)
    return EngCatIndex(tmp_path)


async def test_polysemy_keeps_original_equivalents_and_metadata(index):
    result = await index.cerca("bank")
    assert result["status"] == "ok"
    assert result["match"] == "exact"
    assert result["total"] == result["returned"] == 2
    assert result["data_revision"] == fetch_engcat.DEFAULT_REF
    river, finance = result["accepcions"]
    assert river["ambits"] == ["geografia"]
    assert river["definicio_catalana"] == "Vora d'un riu."
    assert river["equivalents"] == [
        {"forma": "ribera", "categoria": "f", "marques": ["literari"], "nota": "vora d'un riu"},
        {"forma": "riba", "categoria": "f"},
    ]
    assert river["formes_angleses"][1]["marques"] == ["UK"]
    assert river["exemples"] == [{"angles": "On the bank.", "catala": "A la riba."}]
    assert finance["equivalents"] == [{"forma": "banc", "categoria": "m"}]
    limited = await index.cerca("bank", limit=1)
    assert limited["total"] == 2
    assert limited["truncated"]
    assert limited["accepcions"] == [river]


async def test_full_expression_and_case_fallback(index):
    result = await index.cerca("  In spite\tOF ")
    assert result["query"] == {"terme": "In spite OF"}
    assert result["match"] == "case_insensitive"
    assert result["accepcions"][0]["equivalents"][0]["forma"] == "malgrat"
    assert (await index.cerca("Bank"))["total"] == 1


@pytest.mark.parametrize("term", ["very unknown term", "spite", "I ran to the bank.", "unfinished"])
async def test_no_matches(index, term):
    result = await index.cerca(term)
    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert result["accepcions"] == []


async def test_missing_and_corrupt_data_are_not_no_matches(tmp_path):
    index = EngCatIndex(tmp_path)
    with pytest.raises(InvalidQueryError):
        await index.cerca(" ")
    with pytest.raises(DataUnavailableError, match="no està instal·lat"):
        await index.cerca("bank")
    (tmp_path / DATA_FILE).write_bytes(b"corrupt")
    with pytest.raises(DataUnavailableError, match="No es pot llegir"):
        await index.cerca("bank")


async def test_installer_does_not_replace_valid_index_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("LLENGUA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        fetch_engcat.urllib.request, "urlopen", lambda *_a, **_kw: BytesIO(archive())
    )
    assert fetch_engcat.main([]) == 0
    monkeypatch.setattr(
        fetch_engcat.urllib.request, "urlopen", lambda *_a, **_kw: BytesIO(archive("<bad>"))
    )
    assert fetch_engcat.main(["--force"]) == 1
    assert (await EngCatIndex(tmp_path).cerca("bank"))["total"] == 2

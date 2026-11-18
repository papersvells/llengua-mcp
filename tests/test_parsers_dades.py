from __future__ import annotations

from llengua_mcp.parsers.dades import parse_dades


def test_parse_dades_total_and_periods() -> None:
    html = """
    <script>
    function drawChart_total() {
      var data = google.visualization.arrayToDataTable([
        ['dades', 'analitzats', 'noms propis', 'no analitzables', 'altres', { role: 'annotation' }]
        ,['', 102493057, 2344195, 4875907, 16891059, 126604218]
      ]);
    }
    google.charts.setOnLoadCallback(drawChart_total);
    function drawChart_grupscron() {
      var data = google.visualization.arrayToDataTable([
        ['dades', 'analitzats', 'noms propis', 'no analitzables', 'altres', { role: 'annotation' }]
        ,['1832-1913', 45, 10, 5, 0, 13001158],['2021-2022', 307, 10, 5, 0, 12732985]
      ]);
    }
    </script>
    """
    parsed = parse_dades(html)
    assert parsed["total_words"] == 126604218
    assert parsed["analyzed"] == 102493057
    assert parsed["proper_nouns"] == 2344195
    assert len(parsed["periods"]) == 2
    assert parsed["periods"][0]["from_year"] == 1832
    assert parsed["periods"][0]["to_year"] == 1913
    assert parsed["periods"][1]["corpus_units"] == 12732985

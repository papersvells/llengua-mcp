"""Utilitats compartides dels parsers de taules wpDataTables.

La resposta porta `data` amb les files, `recordsTotal` amb el catàleg sencer i
`recordsFiltered` amb les coincidències. Un comptador absent no és un zero: si
no hi ha files, no es pot afirmar cap absència.
"""

from __future__ import annotations

from typing import Any


def count_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_filtered_total(payload: dict[str, Any], results: list[Any]) -> tuple[int | None, bool]:
    """Resol el total filtrat i si és fiable.

    Retorna `(total, verified)`:

    - `recordsFiltered` present i enter → el valor i `True`;
    - absent amb files llegides → el nombre de files i `False`;
    - absent sense files → `None` i `False`: no es pot afirmar cap zero.
    """

    total = count_value(payload.get("recordsFiltered"))
    if total is not None:
        return total, True
    if results:
        return len(results), False
    return None, False


__all__ = ["count_value", "resolve_filtered_total"]

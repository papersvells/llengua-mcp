"""Utilitats compartides dels parsers de taules wpDataTables.

La resposta porta `data` amb les files, `recordsTotal` amb el catàleg sencer i
`recordsFiltered` amb les coincidències. Un comptador absent o invàlid no és un
zero: si no hi ha files, no es pot afirmar cap absència.
"""

from __future__ import annotations

import re
from typing import Any

_DIGITS = re.compile(r"[0-9]+")


def count_value(value: Any) -> int | None:
    """Retorna un comptador vàlid o `None`.

    Només s'accepten enters no negatius i cadenes de dígits. Un booleà, una
    fracció o un negatiu no són un comptador: `False` no és un zero.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        return int(text) if _DIGITS.fullmatch(text) else None
    return None


def resolve_filtered_total(
    payload: dict[str, Any], results: list[Any]
) -> tuple[int | None, bool, str | None]:
    """Resol el total filtrat, si és fiable i, si no ho és, per quin motiu.

    Retorna `(total, verified, reason)`:

    - `recordsFiltered` vàlid → el valor, `True` i `None`;
    - absent amb files llegides → el nombre de files, `False` i
      `records_filtered_missing`;
    - present però invàlid amb files → el nombre de files, `False` i
      `records_filtered_invalid`;
    - absent o invàlid sense files → `None`, `False` i el motiu: no es pot
      afirmar cap zero.
    """

    raw = payload.get("recordsFiltered")
    total = count_value(raw)
    if total is not None:
        return total, True, None
    reason = (
        "records_filtered_invalid" if "recordsFiltered" in payload else "records_filtered_missing"
    )
    if results:
        return len(results), False, reason
    return None, False, reason


__all__ = ["count_value", "resolve_filtered_total"]

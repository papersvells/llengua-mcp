"""Adaptador del diccionari de sinònims de Softcatalà."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from llengua_mcp.config import Settings
from llengua_mcp.sinonims import LICENSE, SOURCE_URL, SinonimsIndex
from llengua_mcp.text import clean_text


class SoftcatalaAdapter:
    def __init__(self, settings: Settings) -> None:
        self.index = SinonimsIndex(settings.data_dir)

    def cerca(
        self,
        paraula: str,
        *,
        context: str | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        paraula = clean_text(paraula)
        result = self.index.lookup(paraula, limit=max(1, min(limit, 50)))
        payload: dict[str, Any] = {
            **result,
            "query": {"paraula": paraula, "context": clean_text(context) if context else None},
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": (
                "Diccionari de sinònims de Softcatalà (Jaume Ortolà i col·laboradors), "
                f"llicència {LICENSE}, consulta feta el "
                + datetime.now(UTC).strftime("%d/%m/%Y")
                + f": {paraula}"
            ),
            "context_note": (
                "Els sinònims són propostes de significat. Si hi ha un context, "
                "cal triar les opcions que hi encaixen i explicar-ne el matís; "
                "no totes són intercanviables."
            )
            if context
            else (
                "Els sinònims són propostes de significat; cal comprovar que "
                "encaixen en la frase concreta."
            ),
            "source": SOURCE_URL,
        }
        return payload


__all__ = ["SoftcatalaAdapter"]

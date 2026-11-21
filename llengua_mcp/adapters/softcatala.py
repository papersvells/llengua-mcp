"""Adaptador del diccionari de sinònims de Softcatalà."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from llengua_mcp.config import Settings
from llengua_mcp.sinonims import LICENSE, SOURCE_URL, SinonimsIndex
from llengua_mcp.text import clean_text


class SoftcatalaAdapter:
    def __init__(self, settings: Settings) -> None:
        self.index = SinonimsIndex(settings.data_dir)
        self._load_lock = asyncio.Lock()

    async def warm(self) -> None:
        """Carrega l'índex en segon pla; la primera consulta no paga la lectura."""

        if self.index.loaded:
            return
        async with self._load_lock:
            if self.index.loaded:
                return
            await asyncio.to_thread(self.index.load)

    async def cerca_async(
        self,
        paraula: str,
        *,
        context: str | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        await self.warm()
        return self.cerca(paraula, context=context, limit=limit)

    def cerca(
        self,
        paraula: str,
        *,
        context: str | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        paraula = clean_text(paraula)
        result = self.index.lookup(
            paraula,
            context=clean_text(context) if context else None,
            limit=max(1, min(limit, 50)),
        )
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
                "Els sinònims són propostes de significat. Amb context, es "
                "prioricen les agrupacions que hi coincideixen (etiqueta de "
                "sentit o formes que hi apareixen); si no n'hi ha cap, l'avís és "
                "`context_no_match`. El diccionari no porta definicions: cal "
                "triar les opcions que hi encaixen i explicar-ne el matís; no "
                "totes són intercanviables."
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

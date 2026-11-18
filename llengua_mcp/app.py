"""Composició de l'aplicació: client, cursors i adaptadors."""

from __future__ import annotations

from llengua_mcp.adapters import (
    BdlexAdapter,
    CtilcAdapter,
    DiecAdapter,
    EsadirAdapter,
    OiecAdapter,
    OptimotAdapter,
    SoftcatalaAdapter,
)
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.http import HttpClient


class App:
    def __init__(self, settings: Settings) -> None:
        settings.ensure_dirs()
        self.settings = settings
        self.http = HttpClient(settings)
        self.cursors = CursorStore(ttl_seconds=settings.cache_ttl_seconds)
        self.bdlex = BdlexAdapter(self.http)
        self.ctilc = CtilcAdapter(self.http, settings, self.cursors)
        self.oiec = OiecAdapter(self.http)
        self.optimot = OptimotAdapter(self.http)
        self.diec = DiecAdapter(self.http)
        self.esadir = EsadirAdapter(self.http)
        self.softcatala = SoftcatalaAdapter(settings)

    async def aclose(self) -> None:
        await self.http.aclose()

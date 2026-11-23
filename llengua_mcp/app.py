"""Composició de l'aplicació: client, cursors i adaptadors."""

from __future__ import annotations

from llengua_mcp.adapters import (
    BdlexAdapter,
    ConjugadorAdapter,
    ConsultesAdapter,
    CtilcAdapter,
    DiecAdapter,
    EsadirAdapter,
    GramatiquesAdapter,
    JaneAdapter,
    OiecAdapter,
    OptimotAdapter,
    PccdAdapter,
    SoftcatalaAdapter,
)
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.engcat import EngCatIndex
from llengua_mcp.http import HttpClient


class App:
    def __init__(self, settings: Settings) -> None:
        settings.ensure_dirs()
        self.settings = settings
        self.http = HttpClient(settings)
        self.cursors = CursorStore(ttl_seconds=settings.cache_ttl_seconds)
        self.bdlex = BdlexAdapter(self.http)
        self.consultes = ConsultesAdapter(self.http)
        self.ctilc = CtilcAdapter(self.http, settings, self.cursors)
        self.oiec = OiecAdapter(self.http)
        self.optimot = OptimotAdapter(self.http)
        self.diec = DiecAdapter(self.http)
        self.esadir = EsadirAdapter(self.http)
        self.gramatiques = GramatiquesAdapter(self.http)
        self.jane = JaneAdapter(self.http)
        self.softcatala = SoftcatalaAdapter(settings)
        self.engcat = EngCatIndex(settings.data_dir)
        self.pccd = PccdAdapter(self.http)
        self.conjugador = ConjugadorAdapter(self.http)

    async def aclose(self) -> None:
        await self.http.aclose()

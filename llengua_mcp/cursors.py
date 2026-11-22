"""Cursors opacs amb TTL per continuar cerques sense dependre del servidor."""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass

from llengua_mcp.models import CursorPayload


@dataclass
class _Entry:
    expires_at: float
    payload: CursorPayload


class CursorStore:
    """Referències aleatòries a un estat local, no IDs remots com a credencials."""

    def __init__(self, *, ttl_seconds: int = 3600, max_entries: int = 200) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, _Entry] = {}
        # Un pany per cursor: dues continuacions del mateix testimoni no poden
        # llegir la mateixa posició abans que cap l'hagi avançada.
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, token: str) -> asyncio.Lock:
        """Retorna el pany d'un cursor existent, per serialitzar-ne les crides."""

        return self._locks.setdefault(token, asyncio.Lock())

    def create(self, payload: CursorPayload) -> str:
        self._purge()
        token = secrets.token_urlsafe(24)
        self._entries[token] = _Entry(time.monotonic() + self.ttl_seconds, payload)
        while len(self._entries) > self.max_entries:
            oldest = min(self._entries, key=lambda key: self._entries[key].expires_at)
            self._entries.pop(oldest, None)
            self._locks.pop(oldest, None)
        return token

    def get(self, token: str) -> CursorPayload | None:
        entry = self._entries.get(token)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._entries.pop(token, None)
            self._locks.pop(token, None)
            return None
        return entry.payload

    def update(self, token: str, payload: CursorPayload) -> None:
        if token in self._entries:
            self._entries[token] = _Entry(time.monotonic() + self.ttl_seconds, payload)

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at < now]
        for key in expired:
            self._entries.pop(key, None)
            self._locks.pop(key, None)

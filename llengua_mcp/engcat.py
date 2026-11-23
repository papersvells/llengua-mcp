"""Índex local del Diccionari anglès-català de Softcatalà."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from unicodedata import normalize

from llengua_mcp.errors import DataUnavailableError, InvalidQueryError, now_iso

DATA_FILE = "engcat.sqlite3"
SOURCE_URL = "https://github.com/Softcatala/diccionari-angles-catala"
LICENSE = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "Diccionari anglès-català de Softcatalà (David Cànovas, Jaume Ortolà i Marc Riera)"
INSTALL_HINT = "Executa `llengua-mcp-fetch-engcat` per instal·lar les dades."
SCHEMA_VERSION = 1


def normalize_term(term: str) -> str:
    return normalize("NFC", " ".join(term.split()))


def lookup_key(term: str) -> str:
    return normalize("NFC", normalize_term(term).casefold())


class EngCatIndex:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / DATA_FILE

    async def cerca(self, terme: str, *, limit: int = 15) -> dict[str, Any]:
        terme = normalize_term(terme)
        if not terme:
            raise InvalidQueryError("Indica un mot o una locució en anglès.")
        return await asyncio.to_thread(self._lookup, terme, max(1, min(limit, 50)))

    def _lookup(self, term: str, limit: int) -> dict[str, Any]:
        if not self.path.is_file():
            raise DataUnavailableError(
                "El diccionari anglès-català local no està instal·lat.", hint=INSTALL_HINT
            )
        try:
            with closing(
                sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
            ) as db:
                if db.execute("PRAGMA user_version").fetchone() != (SCHEMA_VERSION,):
                    raise ValueError("schema version")
                (revision,) = db.execute("SELECT revision FROM dataset").fetchone() or ("",)
                if not revision:
                    raise ValueError("dataset revision")
                rows = self._matches(db, term, limit, exact_case=True)
                match = "exact"
                if not rows:
                    rows = self._matches(db, term, limit, exact_case=False)
                    match = "case_insensitive"
                senses = [json.loads(payload) for payload, _ in rows]
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise DataUnavailableError(
                "No es pot llegir l'índex local del diccionari anglès-català.",
                hint="Torna a instal·lar les dades amb `llengua-mcp-fetch-engcat --force`.",
            ) from exc
        total = rows[0][1] if rows else 0
        return {
            "status": "ok" if rows else "no_matches",
            "query": {"terme": term},
            "match": match if rows else None,
            "total": total,
            "returned": len(senses),
            "truncated": len(senses) < total,
            "accepcions": senses,
            "source": SOURCE_URL,
            "data_revision": revision,
            "data_license": LICENSE_URL,
            "retrieved_at": now_iso(),
            "citation": f"{ATTRIBUTION}, {LICENSE}: {term}",
        }

    @staticmethod
    def _matches(
        db: sqlite3.Connection, term: str, limit: int, *, exact_case: bool
    ) -> list[tuple[str, int]]:
        # Diverses formes angleses poden indexar una mateixa accepció.
        return db.execute(
            """
            WITH matches AS (
                SELECT sense_id, max(priority) AS priority
                FROM forms WHERE lookup_key = ? AND (? IS NULL OR spelling = ?)
                GROUP BY sense_id
            )
            SELECT senses.payload, count(*) OVER ()
            FROM matches JOIN senses ON senses.id = matches.sense_id
            ORDER BY matches.priority DESC, matches.sense_id
            LIMIT ?
            """,
            (lookup_key(term), term if exact_case else None, term, limit),
        ).fetchall()

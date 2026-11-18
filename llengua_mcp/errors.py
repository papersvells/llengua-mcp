"""Errors estructurats i respostes d'error per a les eines MCP."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class LlenguaError(Exception):
    """Error controlat que es pot explicar a l'agent."""

    status = "upstream_error"
    code = "error"

    def __init__(self, message: str, *, hint: str = "", source: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.source = source


class InvalidQueryError(LlenguaError):
    status = "invalid_query"
    code = "invalid_query"


class UpstreamError(LlenguaError):
    status = "upstream_error"
    code = "upstream_error"


class UnexpectedResponseError(LlenguaError):
    status = "unexpected_response"
    code = "unexpected_response"


class DataUnavailableError(LlenguaError):
    status = "unavailable"
    code = "data_unavailable"


class StaleSearchError(LlenguaError):
    status = "stale_search"
    code = "stale_search"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def error_payload(error: LlenguaError, *, source: str | None = None) -> dict[str, Any]:
    """Retorna un error accionable sense amagar-lo dins un resultat buit."""

    payload: dict[str, Any] = {
        "status": error.status,
        "error": {
            "code": error.code,
            "message": error.message,
        },
        "source": source or error.source,
        "retrieved_at": now_iso(),
    }
    if error.hint:
        payload["error"]["hint"] = error.hint
    return payload

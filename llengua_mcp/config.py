"""Configuració del servidor a partir de variables d'entorn."""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from llengua_mcp import __version__

APP_NAME = "llengua-mcp"


def _float_env(names: tuple[str, ...], default: float, *, strictly_positive: bool = True) -> float:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            try:
                value = float(raw.strip().replace(",", "."))
            except ValueError as exc:
                expectation = "finit i positiu" if strictly_positive else "finit"
                raise ValueError(f"`{name}` ha de ser un nombre decimal {expectation}.") from exc
            if not math.isfinite(value) or (strictly_positive and value <= 0):
                expectation = "finit i positiu" if strictly_positive else "finit"
                raise ValueError(f"`{name}` ha de ser un nombre decimal {expectation}.")
            return value
    return default


def _int_env(names: tuple[str, ...], default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            try:
                value = int(raw.strip())
            except ValueError as exc:
                raise ValueError(f"`{name}` ha de ser un enter entre 1 i {sys.maxsize}.") from exc
            if not 1 <= value <= sys.maxsize:
                raise ValueError(f"`{name}` ha de ser un enter entre 1 i {sys.maxsize}.")
            return value
    return default


def _path_env(names: tuple[str, ...], default: Path) -> Path:
    for name in names:
        raw = os.getenv(name)
        if raw:
            return Path(raw).expanduser()
    return default


@dataclass(frozen=True)
class Settings:
    """Paràmetres d'execució del servidor."""

    user_agent: str
    contact: str
    rate_per_second: float
    timeout_seconds: float
    max_response_bytes: int
    max_occurrences: int
    cache_ttl_seconds: int
    data_dir: Path
    cache_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        contact = os.getenv("LLENGUA_CONTACT") or os.getenv("CTILC_CONTACT") or ""
        agent = (
            os.getenv("LLENGUA_USER_AGENT")
            or os.getenv("CTILC_USER_AGENT")
            or f"llengua-mcp/{__version__}"
        )
        if contact and contact not in agent:
            agent = f"{agent} (contacte: {contact})"

        rate = _float_env(("LLENGUA_RATE", "CTILC_RATE"), 1.0, strictly_positive=False)
        # Un ritme més alt no és cortès i pot fer caure el servei.
        rate = max(0.2, min(rate, 1.0))

        return cls(
            user_agent=agent,
            contact=contact,
            rate_per_second=rate,
            timeout_seconds=_float_env(("LLENGUA_TIMEOUT",), 45.0),
            max_response_bytes=_int_env(("LLENGUA_MAX_BYTES",), 4_000_000),
            max_occurrences=_int_env(("LLENGUA_MAX_OCCURRENCES",), 50),
            cache_ttl_seconds=_int_env(("LLENGUA_CACHE_TTL",), 3600),
            data_dir=_path_env(
                ("LLENGUA_DATA_DIR", "CTILC_CACHE_DIR"),
                Path(user_data_dir(APP_NAME)),
            ),
            cache_dir=_path_env(
                ("LLENGUA_CACHE_DIR", "CTILC_CACHE_DIR"),
                Path(user_cache_dir(APP_NAME)),
            ),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

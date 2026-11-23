"""Instal·la una revisió fixada de les dades opcionals del DIRELEX."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from llengua_mcp.config import Settings
from llengua_mcp.direlex import DATA_FILE, REVISION, read_entries

URL = f"https://raw.githubusercontent.com/Softcatala/direlex/{REVISION}/data/data.json.gz"
MAX_BYTES = 4_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Instal·la les dades locals del DIRELEX.")
    parser.add_argument("--force", action="store_true", help="Substitueix les dades existents.")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    destination = settings.data_dir / DATA_FILE
    if destination.exists() and not args.force:
        print(f"Ja existeixen les dades: {destination}. Fes servir --force per reinstal·lar-les.")
        return 0
    request = urllib.request.Request(URL, headers={"User-Agent": settings.user_agent})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("la descàrrega supera el límit de mida")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=settings.data_dir) as staging:
            pending = Path(staging) / DATA_FILE
            pending.write_bytes(data)
            read_entries(pending)
            pending.replace(destination)
    except (OSError, EOFError, ValueError, TypeError) as exc:
        print(f"No s'han pogut instal·lar les dades del DIRELEX: {exc}", file=sys.stderr)
        return 1
    print(f"Dades del DIRELEX instal·lades: {destination} ({REVISION}, CC BY-NC 4.0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

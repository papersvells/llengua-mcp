"""Baixa les dades del diccionari de sinònims de Softcatalà.

Ús:
    python -m llengua_mcp.fetch_sinonims [--ref master] [--force]

Les dades tenen llicència CC BY 4.0 i s'han de citar. El fitxer es desa a
`LLENGUA_DATA_DIR` (per defecte, el directori de dades de l'usuari).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from llengua_mcp.config import Settings
from llengua_mcp.sinonims import DATA_FILE, LICENSE, META_FILE, SOURCE_URL, parse_groups

RAW_URL = "https://raw.githubusercontent.com/softcatala/sinonims-cat/{ref}/dict/sinonims.txt"
MAX_BYTES = 8_000_000
# Commit fixat perquè una instal·lació sigui reproduïble. Per actualitzar:
# `python -m llengua_mcp.fetch_sinonims --ref master --force`.
DEFAULT_REF = "0922f7d6409914cdc4c311f9be3b98282964938f"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baixa el diccionari de sinònims de Softcatalà.")
    parser.add_argument(
        "--ref",
        default=DEFAULT_REF,
        help=(
            "Branca, etiqueta o commit del repositori. Per defecte, el commit "
            "fixat per a instal·lacions reproduïbles."
        ),
    )
    parser.add_argument("--force", action="store_true", help="Sobreescriu les dades existents.")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    data_file = settings.data_dir / DATA_FILE
    meta_file = settings.data_dir / META_FILE

    if data_file.exists() and not args.force:
        print(f"Ja existeixen les dades: {data_file}", file=sys.stderr)
        print("Fes servir --force per tornar-les a baixar.", file=sys.stderr)
        return 0

    url = RAW_URL.format(ref=args.ref)
    request = urllib.request.Request(url, headers={"User-Agent": settings.user_agent})
    print(f"Baixant {url}", file=sys.stderr)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("la baixada supera el límit de mida")
        text = payload.decode("utf-8")
        if not parse_groups(text):
            raise ValueError("la resposta no conté cap grup de sinònims vàlid")

        digest = hashlib.sha256(payload).hexdigest()
        meta = {
            "source": SOURCE_URL,
            "raw_url": url,
            "ref": args.ref,
            "license": LICENSE,
            "sha256": digest,
            "bytes": len(payload),
            "fetched_at": (
                datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            ),
            "attribution": "Diccionari de sinònims de Softcatalà, Jaume Ortolà i col·laboradors.",
        }
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=settings.data_dir) as staging:
            pending_data = Path(staging) / DATA_FILE
            pending_meta = Path(staging) / META_FILE
            pending_data.write_bytes(payload)
            pending_meta.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            pending_data.replace(data_file)
            pending_meta.replace(meta_file)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"No s'han pogut instal·lar les dades de sinònims: {exc}", file=sys.stderr)
        return 1
    print(f"Dades desades a {data_file} ({len(payload)} bytes).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

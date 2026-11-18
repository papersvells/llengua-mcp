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

from llengua_mcp.config import Settings
from llengua_mcp.sinonims import DATA_FILE, LICENSE, META_FILE, SOURCE_URL

RAW_URL = "https://raw.githubusercontent.com/softcatala/sinonims-cat/{ref}/dict/sinonims.txt"
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
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    data_file = settings.data_dir / DATA_FILE
    meta_file = settings.data_dir / META_FILE

    if data_file.exists() and not args.force:
        print(f"Ja existeixen les dades: {data_file}", file=sys.stderr)
        print("Fes servir --force per tornar-les a baixar.", file=sys.stderr)
        return 0

    url = RAW_URL.format(ref=args.ref)
    request = urllib.request.Request(url, headers={"User-Agent": settings.user_agent})
    print(f"Baixant {url}", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    if not payload:
        print("La resposta és buida; no s'escriuen dades.", file=sys.stderr)
        return 1
    data_file.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    meta = {
        "source": SOURCE_URL,
        "raw_url": url,
        "ref": args.ref,
        "license": LICENSE,
        "sha256": digest,
        "bytes": len(payload),
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "attribution": "Diccionari de sinònims de Softcatalà, Jaume Ortolà i col·laboradors.",
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dades desades a {data_file} ({len(payload)} bytes).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Instal·la l'índex local versionat del Diccionari anglès-català."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import closing
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from llengua_mcp.config import Settings
from llengua_mcp.engcat import DATA_FILE, SCHEMA_VERSION, lookup_key, normalize_term

DEFAULT_REF = "2e3ea9f7f8239406d5cea8e6e5b8096e484ab8b9"
ARCHIVE_URL = f"https://codeload.github.com/Softcatala/diccionari-angles-catala/zip/{DEFAULT_REF}"
MAX_ARCHIVE_BYTES = 32_000_000
MAX_XML_BYTES = 64_000_000


def _form(node: ET.Element) -> dict[str, str | list[str]]:
    if not node.text or not node.text.strip():
        raise ValueError("forma lèxica buida")
    result: dict[str, str | list[str]] = {"forma": node.text}
    for source, target in (
        ("class", "categoria"),
        ("grammar", "gramatica"),
        ("remark", "nota"),
        ("inflection", "flexio"),
        ("feminine", "femeni"),
        ("plural", "plural"),
        ("before", "abans"),
        ("after", "despres"),
    ):
        if value := node.get(source):
            result[target] = value
    if tags := node.get("tags"):
        result["marques"] = tags.split()
    if variants := node.get("variants"):
        result["variants"] = [value.strip() for value in variants.split(";") if value.strip()]
    return result


def _store_entry(db: sqlite3.Connection, entry: ET.Element) -> None:
    if entry.get("done") != "yes" or entry.get("type") == "sentence":
        return
    english, catalan = entry.findall("eng"), entry.findall("cat")
    if not english or not catalan:
        raise ValueError("accepció sense formes angleses o catalanes")
    payload = {
        "formes_angleses": [_form(node) for node in english],
        "equivalents": [_form(node) for node in catalan],
        "exemples": [
            {"angles": node.attrib["sent_eng"], "catala": node.attrib["sent_cat"]}
            for node in entry.findall("example")
        ],
    }
    for source, target in (
        ("def_eng", "definicio_anglesa"),
        ("def_cat", "definicio_catalana"),
        ("remark", "nota"),
        ("type", "tipus"),
        ("scientific_name", "nom_cientific"),
    ):
        if value := entry.get(source):
            payload[target] = value
    if areas := entry.get("area"):
        payload["ambits"] = areas.split()

    sense_id = db.execute(
        "INSERT INTO senses (payload) VALUES (?)", (json.dumps(payload, ensure_ascii=False),)
    ).lastrowid
    db.executemany(
        "INSERT INTO forms VALUES (?, ?, ?, ?)",
        (
            (
                lookup_key(spelling),
                normalize_term(spelling),
                sense_id,
                int(node.get("priority", "0")),
            )
            for node in english
            if node.get("no_lemma") != "yes"
            for spelling in (node.text or "",)
        ),
    )


def build_index(archive: bytes, destination: Path, revision: str) -> None:
    with ZipFile(BytesIO(archive)) as files, closing(sqlite3.connect(destination)) as db, db:
        prefix = (f"diccionari-angles-catala-{revision}", "diccionari")
        members = sorted(
            member.filename
            for member in files.infolist()
            if PurePosixPath(member.filename).parts[:-1] == prefix
            and member.filename.endswith(".xml")
        )
        if not members or len(members) != len(set(members)):
            raise ValueError("no hi ha un conjunt vàlid de fitxers XML del diccionari")
        if sum(files.getinfo(name).file_size for name in members) > MAX_XML_BYTES:
            raise ValueError("els fitxers XML superen el límit de mida")
        db.executescript(
            f"""
            PRAGMA user_version = {SCHEMA_VERSION};
            CREATE TABLE dataset (revision TEXT NOT NULL);
            CREATE TABLE senses (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE forms (
                lookup_key TEXT NOT NULL, spelling TEXT NOT NULL,
                sense_id INTEGER NOT NULL, priority INTEGER NOT NULL
            );
            """
        )
        for name in members:
            with files.open(name) as stream:
                root = ET.parse(stream).getroot()
            entries = root.find("entries")
            if root.tag != "root" or entries is None or not entries.findall("e"):
                raise ValueError(f"estructura XML inesperada: {PurePosixPath(name).name}")
            for entry in entries.findall("e"):
                _store_entry(db, entry)
        if db.execute("SELECT 1 FROM forms LIMIT 1").fetchone() is None:
            raise ValueError("el diccionari no conté cap forma anglesa indexable")
        db.execute("CREATE INDEX forms_key ON forms (lookup_key, spelling)")
        db.execute("INSERT INTO dataset VALUES (?)", (revision,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Instal·la el diccionari anglès-català local.")
    parser.add_argument("--force", action="store_true", help="Substitueix les dades existents.")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    destination = settings.data_dir / DATA_FILE
    if destination.exists() and not args.force:
        print(f"Ja existeixen les dades: {destination}. Fes servir --force per reinstal·lar-les.")
        return 0
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": settings.user_agent})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            archive = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise ValueError("el ZIP supera el límit de mida")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=settings.data_dir) as staging:
            pending = Path(staging) / DATA_FILE
            build_index(archive, pending, DEFAULT_REF)
            pending.replace(destination)
    except (
        OSError,
        BadZipFile,
        ET.ParseError,
        RuntimeError,
        sqlite3.Error,
        ValueError,
        KeyError,
    ) as exc:
        print(f"No s'ha pogut instal·lar el diccionari anglès-català: {exc}", file=sys.stderr)
        return 1
    print(f"Diccionari anglès-català instal·lat: {destination} ({DEFAULT_REF}, CC BY 4.0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

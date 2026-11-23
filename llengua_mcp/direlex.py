"""Consulta local del Diccionari de recursos lexicals."""

from __future__ import annotations

import asyncio
import gzip
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

from selectolax.lexbor import LexborHTMLParser

from llengua_mcp.errors import DataUnavailableError, InvalidQueryError, now_iso

DATA_FILE = "direlex.json.gz"
REVISION = "65189f18ba6f633ada3f1dda793ef405d8eec3e6"
SOURCE = "https://direlex.softcatala.org"
LICENSE = "https://creativecommons.org/licenses/by-nc/4.0/"
AUTHORS = "Carles Castellanos i Llorenç i Agustí Mayor i Lloret"
MAX_UNCOMPRESSED = 32_000_000


def key(value: str) -> str:
    return unicodedata.normalize("NFC", " ".join(value.split())).casefold()


def read_entries(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rb") as stream:
        data = stream.read(MAX_UNCOMPRESSED + 1)
    if len(data) > MAX_UNCOMPRESSED:
        raise ValueError("el diccionari supera el límit de mida")
    obj = json.loads(data)
    entries = obj.get("entries") if isinstance(obj, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("manca la llista d'articles")
    for item in entries:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(field), str) or not item[field].strip()
            for field in ("title", "title_display", "content")
        ):
            raise ValueError("article incomplet")
    return entries


def text(node: Any) -> str:
    return " ".join(node.text(separator="", strip=False).split())


def parse_article(content: str) -> dict[str, Any]:
    """Conserva els encapçalaments literals i els apartats, sense inferir sinònims."""
    body = LexborHTMLParser(content).body
    senses: list[dict[str, Any]] = []
    introduction: list[str] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None
    pending: list[str] = []
    node = body.child if body else None
    while node:
        value = text(node)
        strong = node.css_first("strong") if node.tag == "p" else None
        number = text(strong) if strong else ""
        if (
            strong
            and re.fullmatch(r"\d+", number)
            and re.match(rf"^{re.escape(number)}\s*\.", value)
        ):
            current = {
                "numero": int(number),
                "categoria": pending,
                "encapcalament": re.sub(r"^\d+\s*\.\s*", "", value, count=1),
                "apartats": [],
            }
            pending = []
            senses.append(current)
        elif node.tag == "div" and current is not None:
            section: dict[str, Any] | None = None
            for paragraph in node.css("p"):
                ptext = text(paragraph)
                em = paragraph.css_first("em")
                label = text(em) if em else ""
                if re.fullmatch(r"[a-f]", label) and re.match(rf"^{label}\s*\)", ptext):
                    section = {"codi": label, "titol": ptext, "paragrafs": []}
                    current["apartats"].append(section)
                elif ptext:
                    if section is None:
                        section = {"codi": None, "titol": None, "paragrafs": []}
                        current["apartats"].append(section)
                        warnings.append("unclassified_section")
                    section["paragrafs"].append(ptext)
        elif value:
            if current is None:
                introduction.append(value)
            else:
                pending.append(value)
        node = node.next
    if pending and current is not None:
        current["apartats"].append({"codi": None, "titol": None, "paragrafs": pending})
        warnings.append("unclassified_section")
    references = [
        {"text": text(link), "url": SOURCE + link.attributes["href"]}
        for link in body.css("a")
        if link.attributes.get("href", "").startswith("/lema/")
    ]
    if not senses and not references:
        warnings.append("senses_unparsed")
    return {
        "introduccio": introduction,
        "accepcions": senses,
        "remissions": references,
        "warnings": list(dict.fromkeys(warnings)),
    }


class DirelexIndex:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / DATA_FILE
        self._lock = threading.Lock()
        self._signature: tuple[int, int, int, int, int] | None = None
        self._entries_by_key: dict[str, list[tuple[dict[str, str], str]]] = {}

    def _file_signature(self) -> tuple[int, int, int, int, int]:
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _index(self) -> dict[str, list[tuple[dict[str, str], str]]]:
        signature = self._file_signature()
        if signature == self._signature:
            return self._entries_by_key
        with self._lock:
            signature = self._file_signature()
            if signature == self._signature:
                return self._entries_by_key
            while True:
                entries = read_entries(self.path)
                index: dict[str, list[tuple[dict[str, str], str]]] = {}
                for entry in entries:
                    title = text(LexborHTMLParser(entry["title_display"]).body)
                    forms = [title, entry["title"].replace("_", " ")]
                    if "|" in title:
                        forms.extend(title.split("|"))
                    for form_key in dict.fromkeys(key(form) for form in forms):
                        if form_key:
                            index.setdefault(form_key, []).append((entry, title))
                if self._file_signature() == signature:
                    self._entries_by_key = index
                    self._signature = signature
                    return self._entries_by_key
                signature = self._file_signature()

    async def cerca(self, lema: str) -> dict[str, Any]:
        lema = unicodedata.normalize("NFC", " ".join(lema.split()))
        if not lema:
            raise InvalidQueryError("Indica un lema per consultar el DIRELEX.")
        return await asyncio.to_thread(self._lookup, lema)

    def _lookup(self, lema: str) -> dict[str, Any]:
        try:
            matches = self._index().get(key(lema), [])
        except (OSError, EOFError, ValueError, TypeError) as exc:
            raise DataUnavailableError(
                "Les dades locals del DIRELEX no estan disponibles o són il·legibles.",
                hint=(
                    "Executa `llengua-mcp-fetch-direlex` "
                    "(o afegeix `--force` per reinstal·lar-les)."
                ),
            ) from exc
        articles = []
        for entry, title in matches:
            parsed = parse_article(entry["content"])
            articles.append(
                {
                    "lema": title,
                    "url": f"{SOURCE}/lema/{quote(entry['title'], safe='')}",
                    **parsed,
                }
            )
        warnings = list(dict.fromkeys(w for a in articles for w in a["warnings"]))
        return {
            "status": "partial" if warnings else "ok" if articles else "no_matches",
            "query": {"lema": lema},
            "total": len(articles),
            "articles": articles,
            "warnings": warnings,
            "source": SOURCE,
            "data_revision": REVISION,
            "data_license": LICENSE,
            "retrieved_at": now_iso(),
            "citation": f"Diccionari de recursos lexicals (DIRELEX), {AUTHORS}, CC BY-NC 4.0.",
        }

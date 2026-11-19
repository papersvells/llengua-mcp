"""Parsers de la cerca i de les fitxes d'ésAdir."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text

BASE_URL = "https://www.esadir.cat"
_AUDIO_RE = re.compile(r"reprodueixSo\('([^']+)'\)")
_PRON_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")


def _absolute(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return f"https:{href}"
    return urljoin(BASE_URL, href)


def parse_search(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    container = doc.css_first("#resultats") or doc.body
    text = clean_text(container.text(separator="") if container else "")
    count_match = re.search(r"([\d.]+)\s+elements?", text)
    count = int(re.sub(r"[^\d]", "", count_match.group(1))) if count_match else None

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for cell in doc.css("td.divisor.text.element"):
        link = cell.css_first("a")
        if link is None:
            continue
        title = clean_text(link.text())
        href = _absolute(link.attributes.get("href") or "")
        if not title or not href or href in seen:
            continue
        section = ""
        cells = cell.parent
        if cells is not None:
            section_cell = cells.css_first("td.divisor.text.seccio")
            if section_cell is not None:
                section = clean_text(section_cell.text())
        seen.add(href)
        results.append(
            {
                "title": title,
                "section": section,
                "url": href,
                "match": "title",
                "source": "ésAdir",
            }
        )

    for link in doc.css("table.llistaTaula a"):
        title = clean_text(link.text())
        href = _absolute(link.attributes.get("href") or "")
        if not title or not href or href in seen:
            continue
        seen.add(href)
        results.append(
            {
                "title": title,
                "section": "Llibre d'estil",
                "url": href,
                "match": "rest",
                "source": "ésAdir / 3Cat",
            }
        )

    warnings: list[str] = []
    if count is None and not results:
        # La pàgina sense resultats no porta comptador: el bloc `.noResultat`
        # amb «Cap resultat» és el senyal explícit de zero.
        no_result = doc.css_first(".noResultat")
        if no_result is not None and "cap resultat" in clean_text(no_result.text()).casefold():
            count = 0
    if count is None:
        warnings.append("parse_partial")
    if count and not results:
        warnings.append("parse_partial")

    return {
        "count": count,
        "results": results,
        "warnings": list(dict.fromkeys(warnings)),
    }


def parse_fitxa(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    heading = doc.css_first("main h1")
    title = clean_text(heading.text()) if heading else ""
    if not title or title.lower().startswith("resultats de la cerca"):
        return {
            "found": False,
            "title": title,
            "warnings": ["no_entry"],
        }

    labels: list[str] = []
    for link in doc.css("#etiquetes a"):
        label = clean_text(link.text())
        if label and label not in labels:
            labels.append(label)

    pronunciation = []
    for node in doc.css("#pronuncia span.font-family-arial"):
        text = clean_text(node.text())
        match = _PRON_RE.match(text)
        if match:
            pronunciation.append({"variety": match.group(1), "afi": match.group(2)})
    if not pronunciation:
        pron_container = doc.css_first("#pronuncia")
        if pron_container is not None:
            for part in re.split(r"(?=\[[a-z.]{2,5}\])", clean_text(pron_container.text())):
                match = _PRON_RE.match(clean_text(part))
                if match:
                    pronunciation.append({"variety": match.group(1), "afi": match.group(2)})

    audio_urls = []
    for match in _AUDIO_RE.finditer(html):
        url = _absolute(match.group(1))
        if url and url not in audio_urls:
            audio_urls.append(url)

    definitions: list[str] = []
    examples: list[str] = []
    paragraphs = doc.css("main .BlocContingut p")
    if not paragraphs:
        # En alguns fitxers el contenidor es tanca abans de les definicions.
        paragraphs = doc.css("main p")
    for paragraph in paragraphs:
        full = clean_text(paragraph.text(separator=""))
        if not full:
            continue
        strongs = [clean_text(node.text()) for node in paragraph.css("strong")]
        strong_text = " ".join(item for item in strongs if item)
        if strongs and len(strong_text) >= max(1, int(len(full) * 0.75)):
            examples.extend(item for item in strongs if item)
        else:
            definitions.append(full)

    related = []
    seen = set()
    for link in doc.css("main a"):
        href = _absolute(link.attributes.get("href") or "")
        if not href.startswith(BASE_URL):
            continue
        path = href[len(BASE_URL) :]
        if not path.startswith(("/entrades/", "/toponims/", "/nomspropis/", "/filmoteca/")):
            continue
        link_title = clean_text(link.text())
        if not link_title or href in seen:
            continue
        seen.add(href)
        related.append({"title": link_title, "url": href})

    warnings: list[str] = []
    if not definitions and not examples:
        warnings.append("parse_partial")

    return {
        "found": True,
        "title": title,
        "labels": labels,
        "pronunciation": pronunciation,
        "definitions": definitions,
        "examples": examples,
        "related": related,
        "audio_urls": audio_urls,
        "warnings": list(dict.fromkeys(warnings)),
    }

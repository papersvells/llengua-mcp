"""Índex local del diccionari de sinònims de Softcatalà.

Les dades són un fitxer de grups de sinònims amb el format:

    -adj (color): alegre, viu, clar
    -n: mofeta, burleta, ...

Cada línia és un grup; totes les formes del grup són intercanviables en aquell
sentit. Les paraules poden portar una anotació final entre parèntesis.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llengua_mcp.errors import DataUnavailableError
from llengua_mcp.text import clean_text, contains_words, normalize_key

DATA_FILE = "sinonims.txt"
META_FILE = "sinonims.meta.json"
SOURCE_URL = "https://github.com/softcatala/sinonims-cat"
LICENSE = "CC BY 4.0"

_LINE_RE = re.compile(r"^-(?P<head>[^:]+):\s*(?P<body>.+)$")
_HEAD_RE = re.compile(r"^(?P<pos>[\w/]+)\s*(?:\((?P<context>[^)]*)\))?$")
_NOTE_RE = re.compile(r"^(?P<term>.*?)\s*\((?P<note>[^()]*)\)$")


@dataclass
class Synonym:
    form: str
    note: str | None = None

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {"form": self.form}
        if self.note:
            data["note"] = self.note
        return data


@dataclass
class SynonymGroup:
    pos: str
    context: str
    synonyms: list[Synonym] = field(default_factory=list)
    antonyms: list[Synonym] = field(default_factory=list)


class SinonimsIndex:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_file = data_dir / DATA_FILE
        self.meta_file = data_dir / META_FILE
        self.groups: list[SynonymGroup] = []
        self._index: dict[str, list[int]] = {}
        self.meta: dict[str, Any] = {}
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        if self._loaded:
            return
        if not self.data_file.exists():
            raise DataUnavailableError(
                "No hi ha les dades locals del diccionari de sinònims.",
                hint=(
                    "Executa `python -m llengua_mcp.fetch_sinonims` per baixar-les "
                    "del repositori de Softcatalà (llicència CC BY 4.0)."
                ),
                source=SOURCE_URL,
            )
        raw = self.data_file.read_text(encoding="utf-8")
        for line in raw.splitlines():
            line = line.strip()
            if not line or not line.startswith("-"):
                continue
            match = _LINE_RE.match(line)
            if not match:
                continue
            head = clean_text(match.group("head"))
            head_match = _HEAD_RE.match(head)
            if not head_match:
                continue
            pos = head_match.group("pos")
            context = clean_text(head_match.group("context") or "")
            group = SynonymGroup(pos=pos, context=context)
            for item in match.group("body").split(", "):
                item = clean_text(item)
                if not item:
                    continue
                note = None
                note_match = _NOTE_RE.match(item)
                if note_match:
                    item = clean_text(note_match.group("term"))
                    note = clean_text(note_match.group("note"))
                if not item:
                    continue
                synonym = Synonym(form=item, note=note)
                normalized_note = normalize_key(note or "")
                if note and (
                    normalized_note in {"anto", "antonim", "antonims"} or "antònim" in note.lower()
                ):
                    group.antonyms.append(synonym)
                else:
                    group.synonyms.append(synonym)
            if not group.synonyms and not group.antonyms:
                continue
            index = len(self.groups)
            self.groups.append(group)
            for term in group.synonyms + group.antonyms:
                key = normalize_key(term.form)
                if key:
                    self._index.setdefault(key, []).append(index)

        if self.meta_file.exists():
            try:
                self.meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.meta = {}
        self._loaded = True

    @staticmethod
    def _context_score(
        group: SynonymGroup,
        key: str,
        context_key: str,
        context_tokens: set[str],
    ) -> tuple[int, list[str]]:
        """Puntua una agrupació segons el context donat.

        Les etiquetes de sentit (``(cel)``, ``(color)``) i les formes que
        apareixen literalment al context són els senyals disponibles: el
        diccionari no porta definicions, així que no es pot desambiguar més.
        """

        if not context_key:
            return 0, []
        score = 0
        reasons: list[str] = []
        label = normalize_key(group.context)
        if label and set(label.split()) & context_tokens:
            score += 2
            reasons.append("etiqueta")
        for item in group.synonyms + group.antonyms:
            item_key = normalize_key(item.form)
            if not item_key or item_key == key:
                continue
            if " " in item_key:
                if contains_words(context_key, item_key):
                    score += 2
                    reasons.append("forma")
                    break
            elif item_key in context_tokens:
                score += 1
                reasons.append("forma")
                break
        return score, reasons

    def lookup(self, term: str, *, context: str | None = None, limit: int = 15) -> dict[str, Any]:
        self.load()
        key = normalize_key(term)
        group_indexes = self._index.get(key, [])
        if not group_indexes:
            return {
                "status": "no_results",
                "entry": clean_text(term),
                "groups": [],
                "warnings": ["not_found"],
                "note": (
                    "No hi ha cap entrada per a aquesta paraula o expressió. "
                    "No se n'han buscat els components per separat: els sinònims "
                    "d'una part no equivalen als de l'expressió."
                ),
            }

        context_key = normalize_key(context) if context else ""
        context_tokens = set(context_key.split()) if context_key else set()
        ordered: list[tuple[int, int, int, list[str]]] = []
        for order, index in enumerate(group_indexes):
            group = self.groups[index]
            score, reasons = self._context_score(group, key, context_key, context_tokens)
            ordered.append((score, order, index, reasons))
        # Ordenació estable: primer les agrupacions que encaixen amb el context,
        # després les que ja venien abans.
        ordered.sort(key=lambda entry: (-entry[0], entry[1]))

        seen: set[str] = set()
        groups: list[dict[str, Any]] = []
        count = 0
        truncated = False
        matched_groups = 0
        for score, _, index, reasons in ordered:
            if score > 0:
                matched_groups += 1
            group = self.groups[index]
            term_is_antonym = any(normalize_key(item.form) == key for item in group.antonyms)
            if term_is_antonym:
                # Si el mot cercat és l'antònim del grup, les altres formes del
                # grup són els seus contraris, no sinònims seus.
                opposites = []
                for item in group.synonyms:
                    item_key = normalize_key(item.form)
                    if not item_key or item_key == key or item_key in seen:
                        continue
                    if count >= limit:
                        truncated = True
                        break
                    seen.add(item_key)
                    opposites.append(item.payload())
                    count += 1
                if opposites:
                    payload = {
                        "pos": group.pos,
                        "context": group.context,
                        "relation": "antonym",
                        "synonyms": [],
                        "antonyms": opposites,
                        "context_score": score,
                    }
                    if reasons:
                        payload["context_match"] = reasons
                    groups.append(payload)
                continue

            synonyms = []
            for synonym in group.synonyms:
                synonym_key = normalize_key(synonym.form)
                if not synonym_key or synonym_key == key or synonym_key in seen:
                    continue
                if count >= limit:
                    truncated = True
                    break
                seen.add(synonym_key)
                synonyms.append(synonym.payload())
                count += 1
            antonyms = [
                item.payload() for item in group.antonyms if normalize_key(item.form) != key
            ]
            if synonyms or antonyms:
                payload = {
                    "pos": group.pos,
                    "context": group.context,
                    "relation": "synonym",
                    "synonyms": synonyms,
                    "antonyms": antonyms,
                    "context_score": score,
                }
                if reasons:
                    payload["context_match"] = reasons
                groups.append(payload)
            if truncated:
                break

        warnings: list[str] = []
        if truncated:
            warnings.append("truncated")
        if context_key and matched_groups == 0:
            warnings.append("context_no_match")
        return {
            "status": "ok",
            "entry": clean_text(term),
            "groups": groups,
            "warnings": warnings,
            "context_ranked": bool(context_key),
            "context_matches": matched_groups,
            "license": LICENSE,
            "source": SOURCE_URL,
            "data_version": self.meta,
        }

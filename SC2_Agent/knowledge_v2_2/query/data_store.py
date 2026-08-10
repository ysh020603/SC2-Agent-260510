"""Version-aware access to the SC2 2026-07-01 dataset and its evidence corpus."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = ROOT_DIR / "data_sc2_260701"
DEFAULT_DATABASE_PATH = DEFAULT_DATASET_DIR / "data_base_sc2_260701.json"
ENTITY_SECTIONS = ("Ability", "Unit", "Upgrade")
ALL_SECTIONS = (*ENTITY_SECTIONS, "SubOntology")
MARKDOWN_ENTITY_ALIASES = {
    "TemplarArchive": "Templar Archives",
    "OracleStasisTrap": "Stasis Ward",
    "HellionTank": "Hellbat",
    "VikingFighter": "Viking",
    "LurkerDenMP": "Lurker Den",
    "NydusCanal": "Nydus Worm",
    "InfestorTerran": "Infested Terran",
    "LocustMP": "Locust",
    "LurkerMP": "Lurker",
    "SwarmHostMP": "Swarm Host",
}


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


class DatasetStore:
    """Load one immutable dataset release and expose indexed entities and evidence."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        path = Path(database_path).expanduser().resolve()
        if path.is_dir():
            candidates = sorted(path.glob("data_base_sc2_*.json"))
            if not candidates:
                raise FileNotFoundError(f"No data_base_sc2_*.json found in {path}")
            path = candidates[-1]
        if not path.exists():
            raise FileNotFoundError(path)
        self.database_path = path
        self.dataset_dir = path.parent
        self.markdown_dir = (self.dataset_dir / "markdown").resolve()
        self.data: dict[str, list[dict[str, Any]]] = json.loads(path.read_text(encoding="utf-8"))
        manifest_path = self.dataset_dir / "BUILD_MANIFEST.json"
        self.manifest: dict[str, Any] = (
            json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        )
        self._entity_indexes = {
            section: {
                normalize_key(item.get("name")): item
                for item in self.data.get(section, [])
                if item.get("name")
            }
            for section in ALL_SECTIONS
        }
        self._relations = self._collect_relations()
        self._relations_by_id = {
            relation["relation_id"]: relation
            for relation in self._relations
            if relation.get("relation_id")
        }
        self._facts_by_id: dict[str, dict[str, Any]] = {}
        for relation in self._relations:
            for fact in relation.get("fact") or []:
                if fact.get("fact_id"):
                    self._facts_by_id[fact["fact_id"]] = fact
        self._markdown_index = self._build_markdown_index()

    def _collect_relations(self) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for section in ALL_SECTIONS:
            for entity in self.data.get(section, []):
                for relation in entity.get("relations") or []:
                    relation = dict(relation)
                    relation.setdefault("subject_type", section)
                    relation.setdefault("object_type", "")
                    relation["description"] = list_value(relation.get("description"))
                    relation["source"] = list(relation.get("source") or [])
                    relation["fact"] = list(relation.get("fact") or [])
                    signature = relation.get("relation_id") or json.dumps(
                        [
                            relation.get("subject_type"),
                            relation.get("subject_name"),
                            relation.get("relation"),
                            relation.get("object_type"),
                            relation.get("object_name"),
                        ],
                        ensure_ascii=False,
                    )
                    if signature in seen:
                        continue
                    seen.add(signature)
                    collected.append(relation)
        return collected

    def _build_markdown_index(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        if not self.markdown_dir.exists():
            return index
        for path in sorted(self.markdown_dir.rglob("*.md")):
            relative = path.relative_to(self.dataset_dir).as_posix()
            keys = {normalize_key(path.stem)}
            try:
                first = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
                keys.add(normalize_key(first))
            except (IndexError, OSError, UnicodeError):
                pass
            for key in keys:
                index.setdefault(key, []).append(relative)
        for relation in self._relations:
            for fact in relation.get("fact") or []:
                document = fact.get("document")
                if not document:
                    continue
                for value in (fact.get("document_entity"),):
                    if value:
                        index.setdefault(normalize_key(value), []).append(document)
        for canonical, display in MARKDOWN_ENTITY_ALIASES.items():
            if normalize_key(display) in index:
                index.setdefault(normalize_key(canonical), []).extend(index[normalize_key(display)])
        return {key: sorted(set(values)) for key, values in index.items()}

    def items(self, sections: Iterable[str] = ENTITY_SECTIONS) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for section in sections:
            for item in self.data.get(section, []):
                row = dict(item)
                row["_section"] = section
                rows.append(row)
        return rows

    def get_entity(self, section: str, name: str) -> dict[str, Any] | None:
        return self._entity_indexes.get(section, {}).get(normalize_key(name))

    def relations(self) -> list[dict[str, Any]]:
        return self._relations

    def relation(self, relation_id: str) -> dict[str, Any] | None:
        return self._relations_by_id.get(relation_id)

    def fact(self, fact_id: str) -> dict[str, Any] | None:
        return self._facts_by_id.get(fact_id)

    def subontology(self, name: str) -> dict[str, Any] | None:
        return self.get_entity("SubOntology", name)

    def unit_classes(self, unit_name: str) -> list[str]:
        unit = self.get_entity("Unit", unit_name)
        if not unit:
            return []
        direct = list(unit.get("dimension_a_classes") or [])
        race = unit.get("race")
        result = direct + ([race] if race else [])
        result.extend(f"{race}_{value}" for value in direct if race and self.subontology(f"{race}_{value}"))
        return result

    def markdown_documents(self, entity_name: str) -> list[str]:
        return self._markdown_index.get(normalize_key(entity_name), [])

    def safe_markdown_path(self, document: str) -> Path:
        raw = Path(document.replace("\\", "/"))
        candidate = (self.dataset_dir / raw).resolve()
        try:
            candidate.relative_to(self.markdown_dir)
        except ValueError as exc:
            raise ValueError("Markdown document must be inside the dataset markdown directory") from exc
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    def read_markdown(self, document: str, line_start: int = 1, line_end: int | None = None) -> dict[str, Any]:
        path = self.safe_markdown_path(document)
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(1, int(line_start))
        end = min(len(lines), int(line_end or min(start + 40, len(lines))))
        if end < start:
            end = start
        return {
            "document": path.relative_to(self.dataset_dir).as_posix(),
            "line_start": start,
            "line_end": end,
            "content": "\n".join(lines[start - 1 : end]),
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "database_path": str(self.database_path),
            "schema_version": self.manifest.get("schema_version"),
            "generated_at": self.manifest.get("generated_at"),
            "counts": {section: len(self.data.get(section, [])) for section in ALL_SECTIONS},
            "relation_count": len(self._relations),
            "markdown_count": len(list(self.markdown_dir.rglob("*.md"))) if self.markdown_dir.exists() else 0,
        }


def list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


@lru_cache(maxsize=8)
def get_dataset_store(database_path: str | Path = DEFAULT_DATABASE_PATH) -> DatasetStore:
    return DatasetStore(Path(database_path).resolve())


__all__ = [
    "ALL_SECTIONS",
    "DEFAULT_DATABASE_PATH",
    "DEFAULT_DATASET_DIR",
    "DatasetStore",
    "ENTITY_SECTIONS",
    "get_dataset_store",
    "normalize_key",
]

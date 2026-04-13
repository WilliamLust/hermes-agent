from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List

_DEFAULT_REGISTRY_PATHS = [
    Path.home() / '.openclaw' / 'workspace' / 'ACTIVE_PROJECTS.json',
    Path.home() / '.hermes' / 'ACTIVE_PROJECTS.json',
]


@dataclass
class ProjectRecord:
    name: str
    aliases: list[str] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    ports: list[int] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    type: str = 'unknown'


@dataclass
class ProjectMatch:
    project: ProjectRecord
    score: float
    matched_terms: list[str] = field(default_factory=list)
    existing_roots: list[str] = field(default_factory=list)


def _normalize_text(value: str) -> str:
    return ' '.join(value.lower().strip().split())


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def load_project_registry(path: str | Path | None = None) -> list[ProjectRecord]:
    candidates = [Path(path)] if path else _DEFAULT_REGISTRY_PATHS
    payload: dict[str, Any] | None = None
    for candidate in candidates:
        if candidate.exists():
            payload = _read_json(candidate)
            if payload is not None:
                break
    if not payload:
        return []

    projects = payload.get('projects')
    if not isinstance(projects, list):
        return []

    rows: list[ProjectRecord] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        if not isinstance(name, str) or not name.strip():
            continue
        rows.append(
            ProjectRecord(
                name=name.strip(),
                aliases=[str(v).strip() for v in item.get('aliases', []) if str(v).strip()],
                roots=[str(v).strip() for v in item.get('roots', []) if str(v).strip()],
                ports=[int(v) for v in item.get('ports', []) if isinstance(v, (int, float, str)) and str(v).strip().isdigit()],
                urls=[str(v).strip() for v in item.get('urls', []) if str(v).strip()],
                routes=[str(v).strip() for v in item.get('routes', []) if str(v).strip()],
                type=str(item.get('type', 'unknown')).strip() or 'unknown',
            )
        )
    return rows


def _iter_terms(project: ProjectRecord) -> Iterable[str]:
    yield project.name
    for alias in project.aliases:
        yield alias
    for route in project.routes:
        yield route


def score_projects(task_text: str, registry: list[ProjectRecord]) -> list[ProjectMatch]:
    normalized_task = _normalize_text(task_text)
    matches: list[ProjectMatch] = []
    for project in registry:
        score = 0.0
        matched_terms: list[str] = []
        for term in _iter_terms(project):
            normalized_term = _normalize_text(term)
            if normalized_term and normalized_term in normalized_task:
                matched_terms.append(term)
                if term == project.name:
                    score += 0.45
                elif term.startswith('/'):
                    score += 0.25
                else:
                    score += 0.2
        existing_roots = [root for root in project.roots if Path(root).exists()]
        if existing_roots:
            score += 0.1
        if score <= 0:
            continue
        matches.append(
            ProjectMatch(
                project=project,
                score=min(score, 1.0),
                matched_terms=matched_terms,
                existing_roots=existing_roots,
            )
        )
    matches.sort(key=lambda row: row.score, reverse=True)
    return matches

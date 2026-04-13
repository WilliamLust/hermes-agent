from __future__ import annotations

from pathlib import Path
from typing import Any

from acp_adapter.preflight_classifier import classify_task
from acp_adapter.project_registry import load_project_registry, score_projects

_ROUTE_FILE_GLOBS = [
    'src/routes/**/*.ts',
    'src/routes/**/*.tsx',
    'src/screens/**/*.ts',
    'src/screens/**/*.tsx',
    'app/**/*.ts',
    'app/**/*.tsx',
]


def _find_route_candidates(roots: list[str], route_hints: list[str], limit: int = 8) -> list[str]:
    if not route_hints:
        return []
    route_needles = {hint.strip('/').split('/')[-1].lower() for hint in route_hints if hint.strip('/')}
    results: list[str] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for pattern in _ROUTE_FILE_GLOBS:
            for path in root_path.glob(pattern):
                lower_name = path.name.lower()
                parent_lower = str(path).lower()
                if any(needle in lower_name or needle in parent_lower for needle in route_needles):
                    results.append(str(path))
                    if len(results) >= limit:
                        return results
    return results


def build_enrichment_packet(task_text: str) -> dict[str, Any]:
    classification = classify_task(task_text)
    registry = load_project_registry()
    project_matches = score_projects(task_text, registry)

    top_matches = project_matches[:3]
    matched_projects: list[dict[str, Any]] = []
    candidate_roots: list[str] = []
    for match in top_matches:
        roots = match.existing_roots or match.project.roots
        candidate_roots.extend(roots)
        matched_projects.append(
            {
                'name': match.project.name,
                'type': match.project.type,
                'score': round(match.score, 3),
                'matched_terms': match.matched_terms,
                'roots': roots,
                'ports': match.project.ports,
                'routes': match.project.routes,
                'urls': match.project.urls,
            }
        )

    route_candidates = _find_route_candidates(candidate_roots, classification['route_hints'])
    ambiguities: list[str] = []
    if classification['route_hints'] and not route_candidates:
        ambiguities.append('route hinted by user but no matching source candidate found')
    if len(top_matches) > 1 and top_matches[0].score - top_matches[1].score < 0.15:
        ambiguities.append('multiple project roots have similar confidence')

    confidence = 0.15
    if top_matches:
        confidence = max(confidence, top_matches[0].score)
    if route_candidates:
        confidence = min(1.0, confidence + 0.15)
    if ambiguities:
        confidence = max(0.2, confidence - 0.2)

    return {
        'task_type': classification['task_type'],
        'route_hints': classification['route_hints'],
        'matched_hints': classification['matched_hints'],
        'projects': matched_projects,
        'route_candidates': route_candidates,
        'ambiguities': ambiguities,
        'confidence': round(confidence, 3),
        'consult_recommended': confidence < 0.6 or bool(ambiguities),
    }


def render_enrichment_as_system_text(packet: dict[str, Any]) -> str:
    lines = [
        'Proxy preflight context:',
        f"- Task type: {packet.get('task_type', 'unknown')}",
    ]
    route_hints = packet.get('route_hints') or []
    if route_hints:
        lines.append(f"- Route hints: {', '.join(route_hints)}")
    projects = packet.get('projects') or []
    if projects:
        lines.append('- Likely projects:')
        for project in projects[:3]:
            roots = project.get('roots') or []
            roots_text = ', '.join(roots[:2]) if roots else 'none found'
            lines.append(
                f"  - {project.get('name')} (score {project.get('score')}, roots: {roots_text})"
            )
    route_candidates = packet.get('route_candidates') or []
    if route_candidates:
        lines.append('- Route/source candidates:')
        for candidate in route_candidates[:5]:
            lines.append(f'  - {candidate}')
    ambiguities = packet.get('ambiguities') or []
    if ambiguities:
        lines.append('- Ambiguities:')
        for item in ambiguities:
            lines.append(f'  - {item}')
    lines.append('- Use this as discovery guidance only. Verify before editing.')
    return '\n'.join(lines)

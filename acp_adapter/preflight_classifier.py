from __future__ import annotations

import re
from typing import Any

_UI_HINTS = {
    'page', 'screen', 'button', 'modal', 'tab', 'layout', 'route', 'ui', 'ux', 'sidebar', 'nav'
}
_BACKEND_HINTS = {'api', 'endpoint', 'server', 'gateway', 'webhook', 'database'}
_INFRA_HINTS = {'docker', 'deploy', 'proxy', 'tailscale', 'dns', 'ssl', 'infra'}
_CONTENT_HINTS = {'write', 'tweet', 'copy', 'post', 'docs', 'article'}
_PROJECT_HINTS = {'clawsuite', 'hermes', 'landing'}
_ROUTE_RE = re.compile(r'/[a-zA-Z0-9\-_/]+')


def classify_task(task_text: str) -> dict[str, Any]:
    text = task_text.lower().strip()
    route_matches = _ROUTE_RE.findall(task_text)
    matched_hints: list[str] = []

    def _has_any(hints: set[str]) -> bool:
        found = [hint for hint in hints if hint in text]
        matched_hints.extend(found)
        return bool(found)

    task_type = 'unknown'
    if route_matches or _has_any(_UI_HINTS):
        task_type = 'ui'
    elif _has_any(_BACKEND_HINTS):
        task_type = 'backend'
    elif _has_any(_INFRA_HINTS):
        task_type = 'infra'
    elif _has_any(_CONTENT_HINTS):
        task_type = 'content'

    project_hits = [hint for hint in _PROJECT_HINTS if hint in text]
    if len(project_hits) > 1 and task_type != 'ui':
        task_type = 'multi_project'

    return {
        'task_type': task_type,
        'route_hints': route_matches,
        'matched_hints': sorted(set(matched_hints + project_hits)),
    }

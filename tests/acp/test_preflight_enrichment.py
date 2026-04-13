from __future__ import annotations

from acp_adapter.preflight_classifier import classify_task
from acp_adapter.preflight_enrichment import build_enrichment_packet
from acp_adapter.project_registry import ProjectRecord, score_projects


def test_classify_ui_task_with_route_hint() -> None:
    result = classify_task('fix /operations in clawsuite and tweak the page')
    assert result['task_type'] == 'ui'
    assert '/operations' in result['route_hints']


def test_score_projects_prefers_matching_project_and_route() -> None:
    registry = [
        ProjectRecord(
            name='clawsuite',
            aliases=['control ui'],
            roots=['/tmp/does-not-exist'],
            routes=['/operations'],
            type='ui',
        ),
        ProjectRecord(
            name='hermes-workspace',
            aliases=['workspace'],
            roots=['/tmp/does-not-exist-2'],
            routes=['/jobs'],
            type='ui',
        ),
    ]
    matches = score_projects('fix /operations in clawsuite', registry)
    assert matches
    assert matches[0].project.name == 'clawsuite'
    assert '/operations' in matches[0].matched_terms


def test_build_enrichment_packet_returns_projects_and_consult_flag_shape() -> None:
    packet = build_enrichment_packet('fix /operations in clawsuite')
    assert packet['task_type'] == 'ui'
    assert 'projects' in packet
    assert 'consult_recommended' in packet
    assert isinstance(packet['confidence'], float)

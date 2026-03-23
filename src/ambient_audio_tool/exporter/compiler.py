from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ambient_audio_tool import __version__
from ambient_audio_tool.models import (
    AllNode,
    AnyNode,
    AuthoringProject,
    ConditionExpression,
    NotNode,
    PredicateNode,
    RefNode,
    walk_condition_tree,
)

from .models import (
    ExportBundle,
    ExportManifest,
    ExportSummary,
    RuntimeAssetRecord,
    RuntimeConditionRecord,
    RuntimeRuleRecord,
)


EXPORT_FILENAMES = [
    "manifest.json",
    "runtime_rules.json",
    "runtime_conditions.json",
    "runtime_assets.json",
    "export_summary.json",
]


def compile_export_bundle(
    project: AuthoringProject,
    *,
    source_file: str | Path,
) -> ExportBundle:
    source_path = Path(source_file)
    exported_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    sorted_assets = sorted(project.audio_assets, key=lambda item: item.id)
    runtime_assets = [
        RuntimeAssetRecord(
            id=asset.id,
            path=asset.path,
            duration_ms=asset.duration_ms,
        )
        for asset in sorted_assets
    ]

    condition_by_id = {condition.id: condition for condition in project.conditions}
    sorted_condition_ids = sorted(condition_by_id.keys())
    graph = _build_condition_ref_graph(project.conditions)
    transitive_refs = {
        condition_id: _collect_transitive_refs(condition_id, graph)
        for condition_id in sorted_condition_ids
    }

    runtime_conditions = [
        _compile_condition(
            condition_by_id[condition_id],
            direct_refs=sorted(graph.get(condition_id, set())),
            transitive_refs=transitive_refs.get(condition_id, []),
        )
        for condition_id in sorted_condition_ids
    ]

    asset_id_set = {asset.id for asset in project.audio_assets}
    sorted_rules = sorted(project.rules, key=lambda item: item.id)
    runtime_rules = []
    for index, rule in enumerate(sorted_rules, start=1):
        referenced_ids = [rule.condition_ref]
        referenced_ids.extend(
            ref_id for ref_id in transitive_refs.get(rule.condition_ref, []) if ref_id != rule.condition_ref
        )
        runtime_rules.append(
            RuntimeRuleRecord(
                id=rule.id,
                name=rule.name,
                enabled=rule.enabled,
                channel=rule.channel.value,
                condition_ref=rule.condition_ref,
                asset_ids=list(rule.asset_ids),
                priority=rule.priority.model_dump(mode="json"),
                randomness=rule.randomness.model_dump(mode="json"),
                cooldown=rule.cooldown.model_dump(mode="json"),
                conflict=rule.conflict.model_dump(mode="json"),
                referenced_condition_ids=sorted(set(referenced_ids)),
                resolved_asset_count=sum(
                    1 for asset_id in rule.asset_ids if asset_id in asset_id_set
                ),
                export_order=index,
            )
        )

    counts = {
        "rules": len(project.rules),
        "assets": len(project.audio_assets),
        "conditions": len(project.conditions),
        "biome_groups": len(project.biome_groups),
        "custom_events": len(project.custom_events),
    }

    manifest = ExportManifest(
        exporter_version=__version__,
        exported_at_utc=exported_at_utc,
        source_project_id=project.project_id,
        source_project_name=project.project_name,
        source_project_version=project.version,
        source_file=str(source_path),
        counts=counts,
        generated_files=list(EXPORT_FILENAMES),
    )

    summary = ExportSummary(
        output_folder="pending",
        counts=counts,
        generated_files=list(EXPORT_FILENAMES),
    )

    return ExportBundle(
        manifest=manifest,
        runtime_rules=runtime_rules,
        runtime_conditions=runtime_conditions,
        runtime_assets=runtime_assets,
        export_summary=summary,
    )


def _compile_condition(
    condition: ConditionExpression,
    *,
    direct_refs: list[str],
    transitive_refs: list[str],
) -> RuntimeConditionRecord:
    return RuntimeConditionRecord(
        id=condition.id,
        root=_serialize_condition_node(condition.root),
        direct_ref_ids=direct_refs,
        transitive_ref_ids=transitive_refs,
    )


def _serialize_condition_node(node: Any) -> dict[str, Any]:
    if isinstance(node, AllNode):
        return {
            "op": "ALL",
            "nodes": [_serialize_condition_node(child) for child in node.nodes],
        }
    if isinstance(node, AnyNode):
        return {
            "op": "ANY",
            "nodes": [_serialize_condition_node(child) for child in node.nodes],
        }
    if isinstance(node, NotNode):
        return {"op": "NOT", "node": _serialize_condition_node(node.node)}
    if isinstance(node, RefNode):
        return {"op": "REF", "ref_id": node.ref_id}
    if isinstance(node, PredicateNode):
        return {"op": "PRED", "predicate": node.predicate.model_dump(mode="json")}
    raise ValueError(f"Unsupported condition node type: {type(node).__name__}")


def _build_condition_ref_graph(
    conditions: list[ConditionExpression],
) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for condition in conditions:
        graph[condition.id] = {
            node.ref_id
            for node in walk_condition_tree(condition.root)
            if isinstance(node, RefNode)
        }
    return graph


def _collect_transitive_refs(condition_id: str, graph: dict[str, set[str]]) -> list[str]:
    visited: set[str] = set()

    def dfs(node_id: str) -> None:
        for ref_id in sorted(graph.get(node_id, set())):
            if ref_id in visited:
                continue
            visited.add(ref_id)
            dfs(ref_id)

    dfs(condition_id)
    return sorted(visited)

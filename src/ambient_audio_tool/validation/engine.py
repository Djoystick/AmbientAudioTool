from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ambient_audio_tool.io import ProjectLoadError, load_project_source
from ambient_audio_tool.models import (
    AllNode,
    AuthoringProject,
    BiomeInGroupPredicate,
    BiomeIsPredicate,
    ConditionExpression,
    CustomEventPredicate,
    DangerStateIsPredicate,
    PredicateNode,
    RefNode,
    WeatherIsPredicate,
    walk_condition_tree,
)

from .report import Severity, ValidationReport


def validate_authoring_project_file(path: str | Path) -> ValidationReport:
    project, report = load_project_with_report(path)
    if project is None:
        return report
    semantic_report = validate_project(project)
    report.issues.extend(semantic_report.issues)
    return report


def load_project_with_report(
    path: str | Path,
) -> tuple[AuthoringProject | None, ValidationReport]:
    project, report, _meta = load_project_with_report_and_meta(path)
    return project, report


def load_project_with_report_and_meta(
    path: str | Path,
) -> tuple[AuthoringProject | None, ValidationReport, dict[str, str]]:
    report = ValidationReport()
    file_path = Path(path)
    source_meta = {"source_format": "json", "source_note": ""}
    try:
        loaded = load_project_source(file_path)
    except ProjectLoadError as exc:
        report.add(
            Severity.ERROR,
            exc.code,
            str(exc),
            location=exc.location or str(file_path),
        )
        return None, report, source_meta

    raw_data = loaded.payload
    source_meta = {
        "source_format": loaded.source_format,
        "source_note": loaded.source_note,
    }
    for warning in loaded.warnings:
        report.add(
            Severity.WARNING,
            "legacy_import_warning",
            warning,
            location=str(file_path),
        )
    if loaded.source_note:
        report.add(
            Severity.WARNING,
            "legacy_import_info",
            loaded.source_note,
            location=str(file_path),
        )

    try:
        project = AuthoringProject.model_validate(raw_data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            report.add(
                Severity.ERROR,
                "schema_validation_error",
                msg,
                location=f"{file_path}:{loc}" if loc else str(file_path),
            )
        return None, report, source_meta

    return project, report, source_meta


def validate_project(project: AuthoringProject) -> ValidationReport:
    report = ValidationReport()

    _validate_duplicate_ids(report, project)
    _validate_rule_references(report, project)
    _validate_condition_references(report, project)
    _validate_expression_cycles(report, project)
    _validate_obvious_contradictions(report, project)

    return report


def _validate_duplicate_ids(report: ValidationReport, project: AuthoringProject) -> None:
    checks: list[tuple[str, list[object]]] = [
        ("audio_assets", project.audio_assets),
        ("biome_groups", project.biome_groups),
        ("custom_events", project.custom_events),
        ("conditions", project.conditions),
        ("rules", project.rules),
    ]

    for section_name, objects in checks:
        duplicates = _find_duplicate_ids(objects)
        for duplicate in duplicates:
            report.add(
                Severity.ERROR,
                "duplicate_id",
                f"Duplicate id '{duplicate}' found in '{section_name}'.",
                location=section_name,
            )


def _find_duplicate_ids(objects: list[object]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for obj in objects:
        item_id = getattr(obj, "id", None)
        if not item_id:
            continue
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)
    return sorted(duplicates)


def _validate_rule_references(report: ValidationReport, project: AuthoringProject) -> None:
    asset_ids = {asset.id for asset in project.audio_assets}
    condition_ids = {condition.id for condition in project.conditions}

    for rule in project.rules:
        if rule.condition_ref not in condition_ids:
            report.add(
                Severity.ERROR,
                "missing_condition_ref",
                f"Rule '{rule.id}' references missing condition '{rule.condition_ref}'.",
                location=f"rules.{rule.id}.condition_ref",
            )
        for asset_id in rule.asset_ids:
            if asset_id not in asset_ids:
                report.add(
                    Severity.ERROR,
                    "missing_asset_ref",
                    f"Rule '{rule.id}' references missing audio asset '{asset_id}'.",
                    location=f"rules.{rule.id}.asset_ids",
                )


def _validate_condition_references(
    report: ValidationReport, project: AuthoringProject
) -> None:
    condition_ids = {condition.id for condition in project.conditions}
    biome_group_ids = {group.id for group in project.biome_groups}
    custom_event_ids = {event.id for event in project.custom_events}

    for expr in project.conditions:
        for node in walk_condition_tree(expr.root):
            if isinstance(node, RefNode) and node.ref_id not in condition_ids:
                report.add(
                    Severity.ERROR,
                    "missing_expression_ref",
                    f"Condition '{expr.id}' references unknown expression '{node.ref_id}'.",
                    location=f"conditions.{expr.id}",
                )
            if isinstance(node, PredicateNode):
                predicate = node.predicate
                if (
                    isinstance(predicate, BiomeInGroupPredicate)
                    and predicate.group_id not in biome_group_ids
                ):
                    report.add(
                        Severity.ERROR,
                        "missing_biome_group_ref",
                        f"Condition '{expr.id}' references missing biome group "
                        f"'{predicate.group_id}'.",
                        location=f"conditions.{expr.id}",
                    )
                if (
                    isinstance(predicate, CustomEventPredicate)
                    and predicate.event_id not in custom_event_ids
                ):
                    report.add(
                        Severity.ERROR,
                        "missing_custom_event_ref",
                        f"Condition '{expr.id}' references missing custom event "
                        f"'{predicate.event_id}'.",
                        location=f"conditions.{expr.id}",
                    )


def _validate_expression_cycles(report: ValidationReport, project: AuthoringProject) -> None:
    graph: dict[str, set[str]] = {}
    for condition in project.conditions:
        refs = set(_collect_refs(condition))
        graph[condition.id] = refs

    cycles = _find_cycles(graph)
    for cycle in cycles:
        cycle_text = " -> ".join(cycle)
        report.add(
            Severity.ERROR,
            "cyclic_condition_ref",
            f"Cyclic condition references detected: {cycle_text}.",
            location="conditions",
        )


def _collect_refs(condition: ConditionExpression) -> list[str]:
    refs: list[str] = []
    for node in walk_condition_tree(condition.root):
        if isinstance(node, RefNode):
            refs.append(node.ref_id)
    return refs


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        visiting.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in graph:
                continue
            if neighbor in visiting:
                start = stack.index(neighbor)
                cycle = tuple(stack[start:] + [neighbor])
                cycles.add(cycle)
                continue
            if neighbor not in visited:
                dfs(neighbor)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph.keys()):
        if node not in visited:
            dfs(node)

    return [list(cycle) for cycle in sorted(cycles)]


def _validate_obvious_contradictions(
    report: ValidationReport, project: AuthoringProject
) -> None:
    for expr in project.conditions:
        for node in walk_condition_tree(expr.root):
            if not isinstance(node, AllNode):
                continue

            biome_values = set()
            weather_values = set()
            danger_values = set()

            for child in node.nodes:
                if not isinstance(child, PredicateNode):
                    continue
                predicate = child.predicate
                if isinstance(predicate, BiomeIsPredicate):
                    biome_values.add(predicate.biome)
                elif isinstance(predicate, WeatherIsPredicate):
                    weather_values.add(predicate.weather.value)
                elif isinstance(predicate, DangerStateIsPredicate):
                    danger_values.add(predicate.state.value)

            if len(biome_values) > 1:
                report.add(
                    Severity.WARNING,
                    "potentially_unreachable_condition",
                    "ALL node combines multiple biome_is predicates with different values.",
                    location=f"conditions.{expr.id}",
                )
            if len(weather_values) > 1:
                report.add(
                    Severity.WARNING,
                    "potentially_unreachable_condition",
                    "ALL node combines multiple weather_is predicates with different values.",
                    location=f"conditions.{expr.id}",
                )
            if len(danger_values) > 1:
                report.add(
                    Severity.WARNING,
                    "potentially_unreachable_condition",
                    "ALL node combines multiple danger_state_is predicates with different values.",
                    location=f"conditions.{expr.id}",
                )

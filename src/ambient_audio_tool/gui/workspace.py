from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ambient_audio_tool.export import (
    write_js_wrapper_source,
    write_legacy_ambient_config_source,
)
from ambient_audio_tool.exporter import compile_export_bundle, write_export_bundle
from ambient_audio_tool.models import AuthoringProject, ConditionExpression, Rule
from ambient_audio_tool.runtime import RuntimeContext, RuntimeState, simulate_stateful_step
from ambient_audio_tool.validation import (
    ValidationReport,
    load_project_with_report,
    load_project_with_report_and_meta,
    validate_project,
)


@dataclass(frozen=True)
class SimulationRequest:
    biome: str
    time: int
    weather: str
    player_health: int
    is_underwater: bool
    timestamp_ms: int
    repeat: int
    step_ms: int
    seed: int | None


class WorkspaceSession:
    """GUI workspace state and data flow coordinator."""

    def __init__(self) -> None:
        self.project: AuthoringProject | None = None
        self.project_path: Path | None = None
        self.source_format: str = "json"
        self.source_note: str = ""
        self.is_dirty: bool = False

    @property
    def has_project(self) -> bool:
        return self.project is not None

    def load_project(self, path: str | Path) -> ValidationReport:
        project, report, source_meta = load_project_with_report_and_meta(path)
        if project is None:
            return report
        path_obj = Path(path)
        self.project = project
        self.project_path = path_obj
        self.source_format = source_meta.get("source_format", "json")
        self.source_note = source_meta.get("source_note", "")
        self.is_dirty = False
        return report

    def build_view_data(self) -> dict[str, Any]:
        return build_project_view_data(self.require_project())

    def validate(self) -> ValidationReport:
        return validate_project(self.require_project())

    def save_project(self, path: str | Path | None = None) -> Path:
        project = self.require_project()
        target = Path(path) if path is not None else self.project_path
        if target is None:
            raise ValueError("No project path available. Open a file first.")
        if target.suffix.lower() == ".js":
            raise ValueError(
                "Saving to .js is disabled for safety. Use 'Save As JSON' instead."
            )
        payload = project.model_dump(mode="json")
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.project_path = target
        self.source_format = "json"
        self.is_dirty = False
        return target

    def save_project_as_json(self, path: str | Path) -> Path:
        target = Path(path)
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        return self.save_project(target)

    def save_project_as_js_wrapper(self, path: str | Path) -> Path:
        target = Path(path)
        if target.suffix.lower() != ".js":
            target = target.with_suffix(".js")
        write_js_wrapper_source(self.require_project(), target)
        return target

    def save_project_as_legacy_ambient(self, path: str | Path) -> tuple[Path, list[str]]:
        target = Path(path)
        if target.suffix.lower() != ".js":
            target = target.with_suffix(".js")
        result = write_legacy_ambient_config_source(self.require_project(), target)
        return target, result.warnings

    def export(self, output_folder: str | Path) -> dict[str, Any]:
        project = self.require_project()
        source_file = self.project_path or Path("<in-memory-project>")
        bundle = compile_export_bundle(project, source_file=source_file)
        written_files = write_export_bundle(bundle, output_folder)
        return {
            "output_folder": str(Path(output_folder)),
            "generated_files": [path.name for path in written_files],
            "manifest": bundle.manifest.model_dump(mode="json"),
        }

    def run_simulation(self, request: SimulationRequest) -> dict[str, Any]:
        project = self.require_project()
        source_file = self.project_path or Path("<in-memory-project>")
        runtime_bundle = build_runtime_bundle_from_project(project, source_file)
        context = RuntimeContext(
            biome=request.biome,
            time=request.time,
            weather=request.weather,
            player_health=request.player_health,
            is_underwater=request.is_underwater,
        )
        state = RuntimeState(current_time_ms=request.timestamp_ms)
        rng = random.Random(request.seed)

        steps: list[dict[str, Any]] = []
        for step_index in range(request.repeat):
            timestamp_ms = request.timestamp_ms + step_index * request.step_ms
            step_result = simulate_stateful_step(
                runtime_bundle,
                context,
                state,
                timestamp_ms=timestamp_ms,
                rng=rng,
            )
            step_result["step_index"] = step_index + 1
            steps.append(step_result)

        return {
            "request": asdict(request),
            "steps": steps,
            "final_state": state.to_dict(),
        }

    def list_condition_ids(self) -> list[str]:
        return sorted(item.id for item in self.require_project().conditions)

    def list_rule_ids(self) -> list[str]:
        return sorted(item.id for item in self.require_project().rules)

    def list_asset_ids(self) -> list[str]:
        return sorted(item.id for item in self.require_project().audio_assets)

    def get_rule_by_id(self, rule_id: str) -> Rule | None:
        for rule in self.require_project().rules:
            if rule.id == rule_id:
                return rule
        return None

    def get_condition_by_id(self, condition_id: str) -> ConditionExpression | None:
        for condition in self.require_project().conditions:
            if condition.id == condition_id:
                return condition
        return None

    def upsert_rule(
        self,
        rule_payload: dict[str, Any],
        *,
        original_rule_id: str | None = None,
    ) -> Rule:
        project = self.require_project()
        rule = self._validate_rule_payload(rule_payload)
        rules = list(project.rules)

        if original_rule_id is None:
            if any(item.id == rule.id for item in rules):
                raise ValueError(f"Rule id '{rule.id}' already exists.")
            rules.append(rule)
        else:
            replace_index = next(
                (index for index, item in enumerate(rules) if item.id == original_rule_id),
                None,
            )
            if replace_index is None:
                raise ValueError(f"Cannot edit missing rule '{original_rule_id}'.")
            if rule.id != original_rule_id and any(item.id == rule.id for item in rules):
                raise ValueError(f"Rule id '{rule.id}' already exists.")
            rules[replace_index] = rule

        self.project = project.model_copy(update={"rules": rules})
        self.is_dirty = True
        return rule

    def upsert_condition(
        self,
        condition_payload: dict[str, Any],
        *,
        original_condition_id: str | None = None,
    ) -> ConditionExpression:
        project = self.require_project()
        condition = self._validate_condition_payload(condition_payload)
        conditions = list(project.conditions)

        if original_condition_id is None:
            if any(item.id == condition.id for item in conditions):
                raise ValueError(f"Condition id '{condition.id}' already exists.")
            conditions.append(condition)
        else:
            replace_index = next(
                (
                    index
                    for index, item in enumerate(conditions)
                    if item.id == original_condition_id
                ),
                None,
            )
            if replace_index is None:
                raise ValueError(
                    f"Cannot edit missing condition '{original_condition_id}'."
                )
            if condition.id != original_condition_id and any(
                item.id == condition.id for item in conditions
            ):
                raise ValueError(f"Condition id '{condition.id}' already exists.")
            conditions[replace_index] = condition

        self.project = project.model_copy(update={"conditions": conditions})
        self.is_dirty = True
        return condition

    def delete_rule(self, rule_id: str) -> None:
        project = self.require_project()
        if not any(item.id == rule_id for item in project.rules):
            raise ValueError(f"Cannot delete missing rule '{rule_id}'.")
        rules = [item for item in project.rules if item.id != rule_id]
        self.project = project.model_copy(update={"rules": rules})
        self.is_dirty = True

    def condition_references(self, condition_id: str) -> list[str]:
        project = self.require_project()
        return sorted(
            rule.id for rule in project.rules if rule.condition_ref == condition_id
        )

    def delete_condition(self, condition_id: str) -> None:
        project = self.require_project()
        if not any(item.id == condition_id for item in project.conditions):
            raise ValueError(f"Cannot delete missing condition '{condition_id}'.")

        referencing_rules = self.condition_references(condition_id)
        if referencing_rules:
            refs = ", ".join(referencing_rules)
            raise ValueError(
                "Cannot delete condition "
                f"'{condition_id}' because it is used by rule(s): {refs}."
            )

        conditions = [item for item in project.conditions if item.id != condition_id]
        self.project = project.model_copy(update={"conditions": conditions})
        self.is_dirty = True

    def require_project(self) -> AuthoringProject:
        if self.project is None:
            raise ValueError("No project is loaded.")
        return self.project

    @staticmethod
    def _validate_rule_payload(rule_payload: dict[str, Any]) -> Rule:
        try:
            return Rule.model_validate(rule_payload)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            location = ".".join(str(part) for part in first_error.get("loc", []))
            message = first_error.get("msg", "Invalid rule payload.")
            if location:
                raise ValueError(f"Invalid rule field '{location}': {message}") from exc
            raise ValueError(message) from exc

    @staticmethod
    def _validate_condition_payload(
        condition_payload: dict[str, Any],
    ) -> ConditionExpression:
        try:
            return ConditionExpression.model_validate(condition_payload)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            location = ".".join(str(part) for part in first_error.get("loc", []))
            message = first_error.get("msg", "Invalid condition payload.")
            if location:
                raise ValueError(
                    f"Invalid condition field '{location}': {message}"
                ) from exc
            raise ValueError(message) from exc


def load_authoring_project(path: str | Path) -> tuple[AuthoringProject | None, ValidationReport]:
    return load_project_with_report(path)


def validate_authoring_project(project: AuthoringProject) -> ValidationReport:
    return validate_project(project)


def build_project_view_data(project: AuthoringProject) -> dict[str, Any]:
    assets = sorted(
        [
            {
                "id": asset.id,
                "path": asset.path,
                "duration_ms": asset.duration_ms,
            }
            for asset in project.audio_assets
        ],
        key=lambda item: item["id"],
    )
    conditions = sorted(
        [
            {
                "id": condition.id,
                "root_op": condition.root.op,
            }
            for condition in project.conditions
        ],
        key=lambda item: item["id"],
    )
    rules = sorted(
        [
            {
                "id": rule.id,
                "channel": rule.channel.value,
                "condition_ref": rule.condition_ref,
                "asset_count": len(rule.asset_ids),
                "base_priority": rule.priority.base_priority,
            }
            for rule in project.rules
        ],
        key=lambda item: item["id"],
    )
    metadata = {
        "project_id": project.project_id,
        "project_name": project.project_name or "",
        "version": project.version,
        "assets": len(project.audio_assets),
        "conditions": len(project.conditions),
        "rules": len(project.rules),
        "biome_groups": len(project.biome_groups),
        "custom_events": len(project.custom_events),
    }
    return {
        "metadata": metadata,
        "assets": assets,
        "conditions": conditions,
        "rules": rules,
    }


def export_project(
    project: AuthoringProject,
    source_file: str | Path,
    output_folder: str | Path,
) -> dict[str, Any]:
    bundle = compile_export_bundle(project, source_file=source_file)
    written_files = write_export_bundle(bundle, output_folder)
    return {
        "output_folder": str(Path(output_folder)),
        "generated_files": [path.name for path in written_files],
        "manifest": bundle.manifest.model_dump(mode="json"),
    }


def build_runtime_bundle_from_project(
    project: AuthoringProject,
    source_file: str | Path,
) -> dict[str, Any]:
    bundle = compile_export_bundle(project, source_file=source_file)
    return {
        "runtime_rules": [item.model_dump(mode="json") for item in bundle.runtime_rules],
        "runtime_conditions": [
            item.model_dump(mode="json") for item in bundle.runtime_conditions
        ],
        "runtime_assets": [item.model_dump(mode="json") for item in bundle.runtime_assets],
    }


def run_simulation(
    project: AuthoringProject,
    source_file: str | Path,
    request: SimulationRequest,
) -> dict[str, Any]:
    session = WorkspaceSession()
    session.project = project
    session.project_path = Path(source_file)
    return session.run_simulation(request)


def parse_seed_text(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped)


def to_pretty_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)

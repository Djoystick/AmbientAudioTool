from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuntimeAssetRecord(BaseModel):
    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    duration_ms: int | None = Field(default=None, ge=1)


class RuntimeConditionRecord(BaseModel):
    id: str = Field(min_length=1)
    root: dict[str, Any]
    direct_ref_ids: list[str] = Field(default_factory=list)
    transitive_ref_ids: list[str] = Field(default_factory=list)


class RuntimeRuleRecord(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    enabled: bool
    channel: str = Field(min_length=1)
    condition_ref: str = Field(min_length=1)
    asset_ids: list[str] = Field(min_length=1)
    priority: dict[str, Any]
    randomness: dict[str, Any]
    cooldown: dict[str, Any]
    conflict: dict[str, Any]
    referenced_condition_ids: list[str] = Field(default_factory=list)
    resolved_asset_count: int = Field(ge=0)
    export_order: int = Field(ge=1)


class ExportManifest(BaseModel):
    export_format_version: str = "1.0"
    exporter_version: str = Field(min_length=1)
    exported_at_utc: str = Field(min_length=1)
    source_project_id: str = Field(min_length=1)
    source_project_name: str | None = None
    source_project_version: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    counts: dict[str, int]
    generated_files: list[str]


class ExportSummary(BaseModel):
    status: str = "ok"
    message: str = "Export completed successfully."
    output_folder: str = Field(min_length=1)
    counts: dict[str, int]
    generated_files: list[str]


class ExportBundle(BaseModel):
    manifest: ExportManifest
    runtime_rules: list[RuntimeRuleRecord] = Field(default_factory=list)
    runtime_conditions: list[RuntimeConditionRecord] = Field(default_factory=list)
    runtime_assets: list[RuntimeAssetRecord] = Field(default_factory=list)
    export_summary: ExportSummary

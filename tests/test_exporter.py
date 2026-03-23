from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.cli.main import main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

EXPECTED_EXPORT_FILES = {
    "manifest.json",
    "runtime_rules.json",
    "runtime_conditions.json",
    "runtime_assets.json",
    "export_summary.json",
}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_succeeds_on_valid_example(tmp_path: Path, capsys) -> None:
    output_dir = tmp_path / "bundle"
    code = main(
        [
            "export",
            str(EXAMPLES / "biome_music_ref.json"),
            "--out",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Export completed successfully." in captured.out
    assert {item.name for item in output_dir.iterdir()} == EXPECTED_EXPORT_FILES


def test_export_fails_on_invalid_example(tmp_path: Path, capsys) -> None:
    output_dir = tmp_path / "bundle"
    code = main(
        [
            "export",
            str(EXAMPLES / "test_broken_ref.json"),
            "--out",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "Export aborted" in captured.out
    assert not output_dir.exists()


def test_manifest_contains_expected_counts(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"
    code = main(
        [
            "export",
            str(EXAMPLES / "biome_music_ref.json"),
            "--out",
            str(output_dir),
        ]
    )
    assert code == 0

    manifest = _read_json(output_dir / "manifest.json")
    assert manifest["source_project_id"] == "example_biome_music_ref"
    assert manifest["counts"]["rules"] == 1
    assert manifest["counts"]["assets"] == 2
    assert manifest["counts"]["conditions"] == 3
    assert manifest["counts"]["biome_groups"] == 0
    assert manifest["counts"]["custom_events"] == 0
    assert set(manifest["generated_files"]) == EXPECTED_EXPORT_FILES


def test_export_order_is_deterministic(tmp_path: Path) -> None:
    payload = {
        "project_id": "deterministic_order",
        "audio_assets": [
            {"id": "asset_b", "path": "assets/b.ogg"},
            {"id": "asset_a", "path": "assets/a.ogg"},
        ],
        "conditions": [
            {
                "id": "cond_z",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
            },
            {
                "id": "cond_a",
                "root": {"op": "REF", "ref_id": "cond_z"},
            },
        ],
        "rules": [
            {
                "id": "rule_b",
                "channel": "music",
                "condition_ref": "cond_z",
                "asset_ids": ["asset_b", "asset_a"],
            },
            {
                "id": "rule_a",
                "channel": "ambient_noise",
                "condition_ref": "cond_a",
                "asset_ids": ["asset_a"],
            },
        ],
    }
    input_file = tmp_path / "deterministic.json"
    input_file.write_text(json.dumps(payload), encoding="utf-8")

    out_one = tmp_path / "out_one"
    out_two = tmp_path / "out_two"
    assert main(["export", str(input_file), "--out", str(out_one)]) == 0
    assert main(["export", str(input_file), "--out", str(out_two)]) == 0

    rules_one = _read_json(out_one / "runtime_rules.json")
    assets_one = _read_json(out_one / "runtime_assets.json")
    conditions_one = _read_json(out_one / "runtime_conditions.json")

    rules_two = _read_json(out_two / "runtime_rules.json")
    assets_two = _read_json(out_two / "runtime_assets.json")
    conditions_two = _read_json(out_two / "runtime_conditions.json")

    assert [item["id"] for item in rules_one] == ["rule_a", "rule_b"]
    assert [item["id"] for item in assets_one] == ["asset_a", "asset_b"]
    assert [item["id"] for item in conditions_one] == ["cond_a", "cond_z"]
    assert [item["export_order"] for item in rules_one] == [1, 2]

    assert rules_one == rules_two
    assert assets_one == assets_two
    assert conditions_one == conditions_two


def test_runtime_conditions_cleanup_fields_removed(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"
    assert (
        main(
            [
                "export",
                str(EXAMPLES / "biome_music_ref.json"),
                "--out",
                str(output_dir),
            ]
        )
        == 0
    )

    conditions = _read_json(output_dir / "runtime_conditions.json")
    by_id = {item["id"]: item for item in conditions}
    assert "expr_forest_day_music" in by_id
    root_expr = by_id["expr_forest_day_music"]
    assert root_expr["direct_ref_ids"] == ["expr_daytime_clear", "expr_is_forest"]
    assert root_expr["transitive_ref_ids"] == ["expr_daytime_clear", "expr_is_forest"]
    assert "node_count" not in root_expr
    assert "predicate_types" not in root_expr

    rules = _read_json(output_dir / "runtime_rules.json")
    assert rules[0]["referenced_condition_ids"] == [
        "expr_daytime_clear",
        "expr_forest_day_music",
        "expr_is_forest",
    ]
    assert rules[0]["resolved_asset_count"] == 2
    assert rules[0]["export_order"] == 1

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from ambient_audio_tool.export import (
    write_js_wrapper_source,
    write_legacy_ambient_config_source,
)
from ambient_audio_tool.exporter import compile_export_bundle, write_export_bundle
from ambient_audio_tool.runtime import (
    RuntimeContext,
    RuntimeState,
    load_runtime_bundle,
    simulate_stateful_step,
)
from ambient_audio_tool.validation import (
    load_project_with_report,
    validate_authoring_project_file,
    validate_project,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ambient-audio-tool",
        description=(
            "CLI utility for Ambient Audio Tool authoring projects "
            "(validation and runtime export foundation)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an authoring project file (.json or limited .js).",
    )
    validate_parser.add_argument("path", help="Path to project .json or .js file.")

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Print a short summary for a valid project file.",
    )
    summarize_parser.add_argument("path", help="Path to project .json or .js file.")

    export_parser = subparsers.add_parser(
        "export",
        help="Validate and export a project (runtime bundle or selected file format).",
    )
    export_parser.add_argument("path", help="Path to project .json or .js file.")
    export_parser.add_argument(
        "--out",
        required=True,
        help="Output folder (runtime format) or output file/path (other formats).",
    )
    export_parser.add_argument(
        "--format",
        default="runtime",
        choices=["runtime", "json", "js-wrapper", "legacy-ambient"],
        help=(
            "Export format. "
            "'runtime' keeps existing runtime bundle behavior (default)."
        ),
    )

    simulate_parser = subparsers.add_parser(
        "simulate",
        help="Simulate runtime channel selections from an exported runtime folder.",
    )
    simulate_parser.add_argument(
        "runtime_folder",
        help="Folder containing runtime_rules.json, runtime_conditions.json, and runtime_assets.json.",
    )
    simulate_parser.add_argument("--biome", default="minecraft:forest")
    simulate_parser.add_argument("--time", type=int, default=12)
    simulate_parser.add_argument("--weather", default="clear")
    simulate_parser.add_argument("--player-health", type=int, default=20)
    simulate_parser.add_argument("--is-underwater", action="store_true")
    simulate_parser.add_argument(
        "--timestamp-ms",
        type=int,
        default=0,
        help="Timestamp for the first simulation step in milliseconds.",
    )
    simulate_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of stateful steps to simulate.",
    )
    simulate_parser.add_argument(
        "--step-ms",
        type=int,
        default=1000,
        help="Milliseconds to advance between repeated steps.",
    )
    simulate_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for deterministic simulation.",
    )

    return parser


def _cmd_validate(path: str) -> int:
    report = validate_authoring_project_file(Path(path))
    print(report.to_text())
    return 0 if report.is_valid else 1


def _cmd_summarize(path: str) -> int:
    project, report = load_project_with_report(Path(path))
    if project is None:
        print(report.to_text())
        return 1
    print(f"Project: {project.project_id}")
    print(f"Audio assets: {len(project.audio_assets)}")
    print(f"Conditions: {len(project.conditions)}")
    print(f"Rules: {len(project.rules)}")
    print(f"Biome groups: {len(project.biome_groups)}")
    print(f"Custom events: {len(project.custom_events)}")
    return 0


def _cmd_export(path: str, out: str, export_format: str = "runtime") -> int:
    project, report = load_project_with_report(Path(path))
    if project is None:
        print("Export aborted because the input project is invalid.")
        print(report.to_text())
        return 1

    semantic_report = validate_project(project)
    report.issues.extend(semantic_report.issues)
    if not report.is_valid:
        print("Export aborted because validation failed.")
        print(report.to_text())
        return 1

    if report.warning_count > 0:
        print("Validation warnings were found, but export will continue:")
        print(report.to_text())

    if export_format == "runtime":
        bundle = compile_export_bundle(project, source_file=path)
        written_files = write_export_bundle(bundle, out)

        print("Export completed successfully.")
        print(f"Output folder: {Path(out)}")
        print("Generated files:")
        for item in written_files:
            print(f"- {item.name}")
        print(
            "Counts: "
            f"{len(bundle.runtime_rules)} rules, "
            f"{len(bundle.runtime_conditions)} conditions, "
            f"{len(bundle.runtime_assets)} assets."
        )
        return 0

    if export_format == "json":
        target = _resolve_output_file_path(
            out,
            default_filename=f"{project.project_id}.json",
            expected_suffix=".json",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = project.model_dump(mode="json")
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("Export completed successfully.")
        print("Format: json")
        print(f"Output file: {target}")
        return 0

    if export_format == "js-wrapper":
        target = _resolve_output_file_path(
            out,
            default_filename=f"{project.project_id}.js",
            expected_suffix=".js",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        write_js_wrapper_source(project, target)
        print("Export completed successfully.")
        print("Format: js-wrapper")
        print(f"Output file: {target}")
        return 0

    if export_format == "legacy-ambient":
        target = _resolve_output_file_path(
            out,
            default_filename=f"{project.project_id}_legacy_ambient.js",
            expected_suffix=".js",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        result = write_legacy_ambient_config_source(project, target)
        print("Export completed successfully.")
        print("Format: legacy-ambient")
        print(f"Output file: {target}")
        if result.warnings:
            print("Legacy export warnings:")
            for warning in result.warnings:
                print(f"- {warning}")
        return 0

    print(f"Export aborted: unsupported format '{export_format}'.")
    return 1


def _resolve_output_file_path(
    out: str,
    *,
    default_filename: str,
    expected_suffix: str,
) -> Path:
    out_path = Path(out)
    if out_path.exists() and out_path.is_dir():
        return out_path / default_filename
    if out_path.suffix:
        return out_path
    return out_path / default_filename if out_path.is_dir() else out_path.with_suffix(expected_suffix)


def _cmd_simulate(
    runtime_folder: str,
    *,
    biome: str,
    time: int,
    weather: str,
    player_health: int,
    is_underwater: bool,
    timestamp_ms: int,
    repeat: int,
    step_ms: int,
    seed: int | None,
) -> int:
    try:
        context = RuntimeContext(
            biome=biome,
            time=time,
            weather=weather,
            player_health=player_health,
            is_underwater=is_underwater,
        )
    except ValueError as exc:
        print(f"Simulation aborted: {exc}")
        return 1

    if repeat < 1:
        print("Simulation aborted: --repeat must be at least 1.")
        return 1
    if step_ms < 0:
        print("Simulation aborted: --step-ms must be 0 or greater.")
        return 1

    try:
        runtime_bundle = load_runtime_bundle(runtime_folder)
    except FileNotFoundError as exc:
        print(f"Simulation aborted: {exc}")
        return 1
    except ValueError as exc:
        print(f"Simulation aborted: {exc}")
        return 1

    rng = random.Random(seed)
    state = RuntimeState(current_time_ms=timestamp_ms)

    if repeat == 1:
        result = simulate_stateful_step(
            runtime_bundle,
            context,
            state,
            timestamp_ms=timestamp_ms,
            rng=rng,
        )
        print("Simulation result:")
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    step_results: list[dict[str, object]] = []
    for step_index in range(repeat):
        step_timestamp_ms = timestamp_ms + (step_index * step_ms)
        result = simulate_stateful_step(
            runtime_bundle,
            context,
            state,
            timestamp_ms=step_timestamp_ms,
            rng=rng,
        )
        result["step_index"] = step_index + 1
        step_results.append(result)

    print("Timeline simulation results:")
    print(json.dumps(step_results, indent=2, ensure_ascii=False, sort_keys=True))
    print("Final state:")
    print(json.dumps(state.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args.path)
    if args.command == "summarize":
        return _cmd_summarize(args.path)
    if args.command == "export":
        return _cmd_export(args.path, args.out, export_format=args.format)
    if args.command == "simulate":
        return _cmd_simulate(
            args.runtime_folder,
            biome=args.biome,
            time=args.time,
            weather=args.weather,
            player_health=args.player_health,
            is_underwater=args.is_underwater,
            timestamp_ms=args.timestamp_ms,
            repeat=args.repeat,
            step_ms=args.step_ms,
            seed=args.seed,
        )

    parser.print_help()
    return 1


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()

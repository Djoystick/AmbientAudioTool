from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .editors import ConditionEditorDialog, RuleEditorDialog
from .resource_paths import resolve_runtime_path
from .ui_audio_manager import UiAudioManager
from .workspace import (
    SimulationRequest,
    WorkspaceSession,
    parse_seed_text,
    to_pretty_json,
)
from ambient_audio_tool.validation import ValidationReport


class MainWindow(QMainWindow):
    BASE_TITLE = "Ambient Audio Tool - GUI MVP"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.BASE_TITLE)
        self.resize(1220, 900)

        self.workspace = WorkspaceSession()

        self._build_ui()
        self.ui_audio_manager = UiAudioManager(log_callback=self._log)
        self._refresh_ui_music_button()
        self._update_dirty_state_ui()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        top_bar = QHBoxLayout()
        top_bar.addStretch(1)
        self.ui_music_button = QPushButton("")
        self.ui_music_button.clicked.connect(self._on_toggle_ui_music)
        top_bar.addWidget(self.ui_music_button)
        layout.addLayout(top_bar)

        self.tabs = QTabWidget(root)
        layout.addWidget(self.tabs, stretch=1)

        self._build_project_tab()
        self._build_assets_tab()
        self._build_conditions_tab()
        self._build_rules_tab()
        self._build_export_tab()
        self._build_simulation_tab()
        self._build_debug_tab()

        self.log_output = QPlainTextEdit(root)
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(170)
        layout.addWidget(self.log_output)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready.")

    def _build_project_tab(self) -> None:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        top_actions = QHBoxLayout()
        self.open_project_button = QPushButton("Open Project File")
        self.open_project_button.clicked.connect(self._on_open_project)
        self.save_project_button = QPushButton("Save Project")
        self.save_project_button.clicked.connect(self._on_save_project)
        self.save_as_format_combo = QComboBox()
        self.save_as_format_combo.addItem("JSON (Recommended)", "json")
        self.save_as_format_combo.addItem("JS Wrapper", "js-wrapper")
        self.save_as_format_combo.addItem("Legacy AMBIENT_CONFIG", "legacy-ambient")
        self.save_as_json_button = QPushButton("Save As...")
        self.save_as_json_button.clicked.connect(self._on_save_project_as_json)
        self.validate_project_button = QPushButton("Validate Project")
        self.validate_project_button.clicked.connect(self._on_validate_project)
        top_actions.addWidget(self.open_project_button)
        top_actions.addWidget(self.save_project_button)
        top_actions.addWidget(self.save_as_format_combo)
        top_actions.addWidget(self.save_as_json_button)
        top_actions.addWidget(self.validate_project_button)
        top_actions.addStretch(1)
        outer.addLayout(top_actions)

        self.project_path_label = QLabel("Path: (none)")
        self.project_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.project_path_label)

        metadata_box = QGroupBox("Project Metadata")
        metadata_layout = QFormLayout(metadata_box)
        self.meta_project_id = QLabel("-")
        self.meta_project_name = QLabel("-")
        self.meta_project_version = QLabel("-")
        self.meta_source_format = QLabel("-")
        self.meta_counts = QLabel("-")
        metadata_layout.addRow("Project ID:", self.meta_project_id)
        metadata_layout.addRow("Project Name:", self.meta_project_name)
        metadata_layout.addRow("Version:", self.meta_project_version)
        metadata_layout.addRow("Source Format:", self.meta_source_format)
        metadata_layout.addRow("Counts:", self.meta_counts)
        outer.addWidget(metadata_box)

        self.project_summary_output = QPlainTextEdit()
        self.project_summary_output.setReadOnly(True)
        outer.addWidget(self.project_summary_output, stretch=1)

        self.tabs.addTab(tab, "Project")

    def _build_assets_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.assets_table = self._create_table(["id", "path", "duration_ms"])
        layout.addWidget(self.assets_table)
        self.tabs.addTab(tab, "Assets")

    def _build_conditions_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        self.create_condition_button = QPushButton("Create New Condition")
        self.create_condition_button.setToolTip("Create a condition used by rules.")
        self.create_condition_button.clicked.connect(self._on_create_condition)
        actions.addWidget(self.create_condition_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.conditions_table = self._create_table(["id", "root_op", "edit", "delete"])
        layout.addWidget(self.conditions_table)
        self.tabs.addTab(tab, "Conditions")

    def _build_rules_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        self.create_rule_button = QPushButton("Create New Rule")
        self.create_rule_button.setToolTip("Create a rule that maps a condition to assets.")
        self.create_rule_button.clicked.connect(self._on_create_rule)
        actions.addWidget(self.create_rule_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.rules_table = self._create_table(
            [
                "id",
                "channel",
                "condition_ref",
                "asset_count",
                "base_priority",
                "edit",
                "delete",
            ]
        )
        layout.addWidget(self.rules_table)
        self.tabs.addTab(tab, "Rules")

    def _build_export_tab(self) -> None:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        row = QHBoxLayout()
        self.export_output_path = QLineEdit(str(Path.cwd() / "out" / "gui_export"))
        self.export_output_path.setPlaceholderText("Select export output folder")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_choose_export_folder)
        self.export_button = QPushButton("Run Export")
        self.export_button.setToolTip("Generate runtime JSON export files.")
        self.export_button.clicked.connect(self._on_export_project)
        row.addWidget(QLabel("Output Folder:"))
        row.addWidget(self.export_output_path, stretch=1)
        row.addWidget(browse)
        row.addWidget(self.export_button)
        outer.addLayout(row)

        self.export_result_output = QPlainTextEdit()
        self.export_result_output.setReadOnly(True)
        outer.addWidget(self.export_result_output, stretch=1)

        self.tabs.addTab(tab, "Export")

    def _build_simulation_tab(self) -> None:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        controls_box = QGroupBox("Simulation Context")
        controls_layout = QGridLayout(controls_box)

        self.sim_biome_input = QLineEdit("minecraft:forest")
        self.sim_time_input = QSpinBox()
        self.sim_time_input.setRange(0, 23)
        self.sim_time_input.setValue(12)
        self.sim_weather_input = QComboBox()
        self.sim_weather_input.setEditable(True)
        self.sim_weather_input.addItems(["clear", "rain", "thunder", "snow"])
        self.sim_player_health_input = QSpinBox()
        self.sim_player_health_input.setRange(0, 100)
        self.sim_player_health_input.setValue(20)
        self.sim_underwater_input = QCheckBox("Is Underwater")
        self.sim_timestamp_input = QSpinBox()
        self.sim_timestamp_input.setRange(0, 2_000_000_000)
        self.sim_timestamp_input.setValue(0)
        self.sim_repeat_input = QSpinBox()
        self.sim_repeat_input.setRange(1, 10_000)
        self.sim_repeat_input.setValue(1)
        self.sim_step_ms_input = QSpinBox()
        self.sim_step_ms_input.setRange(0, 2_000_000_000)
        self.sim_step_ms_input.setValue(1000)
        self.sim_seed_input = QLineEdit("")
        self.sim_seed_input.setPlaceholderText("Optional integer seed")

        controls_layout.addWidget(QLabel("Biome"), 0, 0)
        controls_layout.addWidget(self.sim_biome_input, 0, 1)
        controls_layout.addWidget(QLabel("Time (0-23)"), 0, 2)
        controls_layout.addWidget(self.sim_time_input, 0, 3)
        controls_layout.addWidget(QLabel("Weather"), 1, 0)
        controls_layout.addWidget(self.sim_weather_input, 1, 1)
        controls_layout.addWidget(QLabel("Player Health"), 1, 2)
        controls_layout.addWidget(self.sim_player_health_input, 1, 3)
        controls_layout.addWidget(self.sim_underwater_input, 2, 0)
        controls_layout.addWidget(QLabel("Timestamp ms"), 2, 2)
        controls_layout.addWidget(self.sim_timestamp_input, 2, 3)
        controls_layout.addWidget(QLabel("Repeat"), 3, 0)
        controls_layout.addWidget(self.sim_repeat_input, 3, 1)
        controls_layout.addWidget(QLabel("Step ms"), 3, 2)
        controls_layout.addWidget(self.sim_step_ms_input, 3, 3)
        controls_layout.addWidget(QLabel("Seed"), 4, 0)
        controls_layout.addWidget(self.sim_seed_input, 4, 1, 1, 3)

        outer.addWidget(controls_box)

        self.simulate_button = QPushButton("Run Simulation")
        self.simulate_button.setToolTip("Run simulation with the current project and context.")
        self.simulate_button.clicked.connect(self._on_run_simulation)
        outer.addWidget(self.simulate_button, alignment=Qt.AlignLeft)

        self.sim_result_hint = QLabel("Results are shown in the Debug / Results tab.")
        outer.addWidget(self.sim_result_hint)
        outer.addStretch(1)

        self.tabs.addTab(tab, "Simulation")

    def _build_debug_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.debug_output = QPlainTextEdit()
        self.debug_output.setReadOnly(True)
        layout.addWidget(self.debug_output)
        self.tabs.addTab(tab, "Debug / Results")

    def _create_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _set_table_rows(
        self, table: QTableWidget, columns: list[str], rows: list[dict]
    ) -> None:
        table.clearContents()
        table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, col_name in enumerate(columns):
                value = row_data.get(col_name, "")
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()

    def _refresh_project_views(self) -> None:
        if not self.workspace.has_project:
            return
        view = self.workspace.build_view_data()
        meta = view["metadata"]

        self.meta_project_id.setText(str(meta["project_id"]))
        self.meta_project_name.setText(str(meta["project_name"] or "-"))
        self.meta_project_version.setText(str(meta["version"]))
        self.meta_source_format.setText(self._source_format_text())
        self.meta_counts.setText(
            "assets={assets}, conditions={conditions}, rules={rules}, "
            "biome_groups={biome_groups}, custom_events={custom_events}".format(**meta)
        )

        self._set_table_rows(
            self.assets_table,
            ["id", "path", "duration_ms"],
            view["assets"],
        )
        self._populate_conditions_table(view["conditions"])
        self._populate_rules_table(view["rules"])
        self._update_dirty_state_ui()
        self._update_action_states()

    def _populate_conditions_table(self, rows: list[dict]) -> None:
        self.conditions_table.clearContents()
        self.conditions_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            condition_id = str(row.get("id", ""))
            self.conditions_table.setItem(row_index, 0, QTableWidgetItem(condition_id))
            self.conditions_table.setItem(
                row_index, 1, QTableWidgetItem(str(row.get("root_op", "")))
            )
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(
                lambda _checked=False, cid=condition_id: self._on_edit_condition(cid)
            )
            self.conditions_table.setCellWidget(row_index, 2, edit_button)
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(
                lambda _checked=False, cid=condition_id: self._on_delete_condition(cid)
            )
            self.conditions_table.setCellWidget(row_index, 3, delete_button)
        self.conditions_table.resizeColumnsToContents()

    def _populate_rules_table(self, rows: list[dict]) -> None:
        self.rules_table.clearContents()
        self.rules_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            rule_id = str(row.get("id", ""))
            self.rules_table.setItem(row_index, 0, QTableWidgetItem(rule_id))
            self.rules_table.setItem(
                row_index, 1, QTableWidgetItem(str(row.get("channel", "")))
            )
            self.rules_table.setItem(
                row_index, 2, QTableWidgetItem(str(row.get("condition_ref", "")))
            )
            self.rules_table.setItem(
                row_index, 3, QTableWidgetItem(str(row.get("asset_count", "")))
            )
            self.rules_table.setItem(
                row_index, 4, QTableWidgetItem(str(row.get("base_priority", "")))
            )
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(
                lambda _checked=False, rid=rule_id: self._on_edit_rule(rid)
            )
            self.rules_table.setCellWidget(row_index, 5, edit_button)
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(
                lambda _checked=False, rid=rule_id: self._on_delete_rule(rid)
            )
            self.rules_table.setCellWidget(row_index, 6, delete_button)
        self.rules_table.resizeColumnsToContents()

    def _on_open_project(self) -> None:
        if not self._confirm_discard_unsaved_changes():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Authoring Project",
            str(resolve_runtime_path("examples")),
            "Project Files (*.json *.js);;JSON Files (*.json);;JavaScript Files (*.js)",
        )
        if not file_path:
            return

        report = self.workspace.load_project(file_path)
        if not self.workspace.has_project:
            self._show_user_error(
                "Open Project Failed",
                "Could not load project file.",
                report.to_text(),
            )
            self.project_summary_output.setPlainText(report.to_text())
            self._show_debug_section("Validation Output", report.to_text())
            self._update_action_states()
            return

        self.project_path_label.setText(f"Path: {file_path}")
        self._refresh_project_views()
        semantic_report = self.workspace.validate()
        combined_report = ValidationReport()
        combined_report.issues.extend(report.issues)
        combined_report.issues.extend(semantic_report.issues)
        summary_text = combined_report.to_text()
        if self.workspace.source_note:
            summary_text = f"{self.workspace.source_note}\n\n{summary_text}"
        self.project_summary_output.setPlainText(summary_text)
        self._show_debug_section("Validation Output", summary_text)
        self._log(f"Loaded project: {file_path}")
        if self.workspace.source_format == "legacy_js":
            self.statusBar().showMessage("Legacy AMBIENT_CONFIG imported successfully.")
        else:
            self.statusBar().showMessage("Project loaded.")

    def _on_toggle_ui_music(self) -> None:
        self.ui_audio_manager.toggle()
        self._refresh_ui_music_button()
        if not self.ui_audio_manager.is_available():
            self.statusBar().showMessage("UI background music is unavailable.")
            return
        self.statusBar().showMessage(
            "UI background music enabled."
            if self.ui_audio_manager.is_enabled()
            else "UI background music disabled."
        )

    def _refresh_ui_music_button(self) -> None:
        if self.ui_audio_manager.is_available():
            if self.ui_audio_manager.is_enabled():
                self.ui_music_button.setText("UI Music: ON")
            else:
                self.ui_music_button.setText("UI Music: OFF")
            self.ui_music_button.setEnabled(True)
            self.ui_music_button.setToolTip("Toggle background UI music.")
            return

        self.ui_music_button.setText("UI Music: OFF")
        self.ui_music_button.setEnabled(False)
        reason = self.ui_audio_manager.disabled_reason() or "UI music unavailable."
        self.ui_music_button.setToolTip(reason)

    def _on_save_project(self) -> None:
        self._save_current_project(show_success=True)

    def _on_save_project_as_json(self) -> None:
        selected_format = self._selected_save_as_format()
        if selected_format == "json":
            self._save_project_as_json_dialog()
            return
        if selected_format == "js-wrapper":
            self._save_project_as_js_wrapper_dialog()
            return
        if selected_format == "legacy-ambient":
            self._save_project_as_legacy_ambient_dialog()
            return
        self._show_user_error("Unsupported Format", f"Unknown save format '{selected_format}'.")

    def _save_project_as_json_dialog(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project file before saving.",
            )
            return
        default_name = "project.json"
        if self.workspace.project_path is not None:
            default_name = f"{self.workspace.project_path.stem}.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As JSON",
            str((Path.cwd() / default_name).resolve()),
            "JSON Files (*.json)",
        )
        if not save_path:
            return
        try:
            saved_path = self.workspace.save_project_as_json(save_path)
        except Exception as exc:
            self._show_user_error(
                "Save As JSON Failed",
                "Could not save project as JSON.",
                str(exc),
            )
            return

        self.project_path_label.setText(f"Path: {saved_path}")
        validation_report = self.workspace.validate()
        self.project_summary_output.setPlainText(validation_report.to_text())
        self._show_debug_section("Validation Output", validation_report.to_text())
        self._update_dirty_state_ui()
        self._log(f"Project saved as JSON: {saved_path}")
        self.statusBar().showMessage("Project saved as JSON.")

    def _save_project_as_js_wrapper_dialog(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project file before saving.",
            )
            return
        default_name = "project.js"
        if self.workspace.project_path is not None:
            default_name = f"{self.workspace.project_path.stem}.js"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As JS Wrapper",
            str((Path.cwd() / default_name).resolve()),
            "JavaScript Files (*.js)",
        )
        if not save_path:
            return
        try:
            saved_path = self.workspace.save_project_as_js_wrapper(save_path)
        except Exception as exc:
            self._show_user_error(
                "Save As JS Wrapper Failed",
                "Could not export project as JS Wrapper.",
                str(exc),
            )
            return

        summary = {
            "format": "js-wrapper",
            "output_file": str(saved_path),
        }
        self._show_debug_section(
            "Project Save As Output",
            f"Saved as JS Wrapper: {saved_path}",
            payload=summary,
        )
        self._log(f"Project exported as JS Wrapper: {saved_path}")
        self.statusBar().showMessage("Project exported as JS Wrapper.")

    def _save_project_as_legacy_ambient_dialog(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project file before saving.",
            )
            return

        response = QMessageBox.warning(
            self,
            "Legacy Export Warning",
            (
                "Legacy AMBIENT_CONFIG export is best-effort and lossy.\n"
                "Some modern rules/conditions may be downgraded or dropped.\n\n"
                "Continue with legacy export?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return

        default_name = "project_legacy_ambient.js"
        if self.workspace.project_path is not None:
            default_name = f"{self.workspace.project_path.stem}_legacy_ambient.js"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As Legacy AMBIENT_CONFIG",
            str((Path.cwd() / default_name).resolve()),
            "JavaScript Files (*.js)",
        )
        if not save_path:
            return
        try:
            saved_path, warnings = self.workspace.save_project_as_legacy_ambient(save_path)
        except Exception as exc:
            self._show_user_error(
                "Legacy Export Failed",
                "Could not export project as legacy AMBIENT_CONFIG.",
                str(exc),
            )
            return

        summary_lines = [f"Saved as legacy AMBIENT_CONFIG: {saved_path}"]
        if warnings:
            summary_lines.append("Warnings:")
            summary_lines.extend(f"- {item}" for item in warnings)

        self._show_debug_section(
            "Project Save As Output",
            "\n".join(summary_lines),
            payload={"format": "legacy-ambient", "output_file": str(saved_path), "warnings": warnings},
        )
        self._log(f"Project exported as legacy AMBIENT_CONFIG: {saved_path}")
        if warnings:
            self._show_user_error(
                "Legacy Export Completed with Warnings",
                "Legacy export finished with downgrade warnings.",
                "\n".join(warnings),
            )
            self.statusBar().showMessage(
                "Legacy export completed with warnings."
            )
            return
        self.statusBar().showMessage("Legacy export completed.")

    def _selected_save_as_format(self) -> str:
        value = self.save_as_format_combo.currentData()
        return str(value) if value is not None else "json"

    def _save_current_project(self, *, show_success: bool) -> bool:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project JSON file before saving.",
            )
            return False
        try:
            saved_path = self.workspace.save_project()
        except Exception as exc:
            self._show_user_error(
                "Save Failed",
                "Could not save the project file.",
                str(exc),
            )
            return False

        self.project_path_label.setText(f"Path: {saved_path}")
        validation_report = self.workspace.validate()
        self.project_summary_output.setPlainText(validation_report.to_text())
        self._show_debug_section("Validation Output", validation_report.to_text())
        self._update_dirty_state_ui()
        self._log(f"Project saved: {saved_path}")
        if show_success:
            self.statusBar().showMessage("Project saved.")
        return True

    def _on_validate_project(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project JSON file before validating.",
            )
            return
        report = self.workspace.validate()
        self.project_summary_output.setPlainText(report.to_text())
        self._show_debug_section("Validation Output", report.to_text())
        if report.is_valid:
            self.statusBar().showMessage("Validation succeeded.")
            self._log("Validation succeeded.")
        else:
            self.statusBar().showMessage("Validation completed with errors.")
            self._log(
                f"Validation found {report.error_count} error(s) and {report.warning_count} warning(s)."
            )

    def _on_create_rule(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error("No Project Loaded", "Open a project first.")
            return
        dialog = RuleEditorDialog(
            condition_ids=self.workspace.list_condition_ids(),
            asset_ids=self.workspace.list_asset_ids(),
            existing_rule_ids=self.workspace.list_rule_ids(),
            existing_rule=None,
            parent=self,
        )
        if dialog.exec() != dialog.Accepted or dialog.saved_payload is None:
            return
        try:
            self.workspace.upsert_rule(dialog.saved_payload)
        except ValueError as exc:
            self._show_user_error("Rule Save Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Created rule: {dialog.saved_payload['id']}")
        self.statusBar().showMessage("Rule created.")

    def _on_edit_rule(self, rule_id: str) -> None:
        if not self.workspace.has_project:
            return
        rule = self.workspace.get_rule_by_id(rule_id)
        if rule is None:
            self._show_user_error("Missing Rule", f"Rule '{rule_id}' was not found.")
            return
        dialog = RuleEditorDialog(
            condition_ids=self.workspace.list_condition_ids(),
            asset_ids=self.workspace.list_asset_ids(),
            existing_rule_ids=self.workspace.list_rule_ids(),
            existing_rule=rule,
            parent=self,
        )
        if dialog.exec() != dialog.Accepted or dialog.saved_payload is None:
            return
        try:
            self.workspace.upsert_rule(
                dialog.saved_payload,
                original_rule_id=rule_id,
            )
        except ValueError as exc:
            self._show_user_error("Rule Save Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Edited rule: {rule_id}")
        self.statusBar().showMessage("Rule updated.")

    def _on_create_condition(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error("No Project Loaded", "Open a project first.")
            return
        dialog = ConditionEditorDialog(
            existing_condition_ids=self.workspace.list_condition_ids(),
            existing_condition=None,
            parent=self,
        )
        if dialog.exec() != dialog.Accepted or dialog.saved_payload is None:
            return
        try:
            self.workspace.upsert_condition(dialog.saved_payload)
        except ValueError as exc:
            self._show_user_error("Condition Save Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Created condition: {dialog.saved_payload['id']}")
        self.statusBar().showMessage("Condition created.")

    def _on_edit_condition(self, condition_id: str) -> None:
        if not self.workspace.has_project:
            return
        condition = self.workspace.get_condition_by_id(condition_id)
        if condition is None:
            self._show_user_error(
                "Missing Condition", f"Condition '{condition_id}' was not found."
            )
            return
        dialog = ConditionEditorDialog(
            existing_condition_ids=self.workspace.list_condition_ids(),
            existing_condition=condition,
            parent=self,
        )
        if dialog.exec() != dialog.Accepted or dialog.saved_payload is None:
            return
        try:
            self.workspace.upsert_condition(
                dialog.saved_payload,
                original_condition_id=condition_id,
            )
        except ValueError as exc:
            self._show_user_error("Condition Save Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Edited condition: {condition_id}")
        self.statusBar().showMessage("Condition updated.")

    def _on_delete_rule(self, rule_id: str) -> None:
        if not self.workspace.has_project:
            return
        response = QMessageBox.question(
            self,
            "Delete Rule",
            f"Delete rule '{rule_id}'?\nThis cannot be undone in the current session.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return
        try:
            self.workspace.delete_rule(rule_id)
        except ValueError as exc:
            self._show_user_error("Delete Rule Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Deleted rule: {rule_id}")
        self.statusBar().showMessage(f"Rule '{rule_id}' deleted.")

    def _on_delete_condition(self, condition_id: str) -> None:
        if not self.workspace.has_project:
            return

        referencing_rules = self.workspace.condition_references(condition_id)
        if referencing_rules:
            refs = ", ".join(referencing_rules)
            self._show_user_error(
                "Cannot Delete Condition",
                (
                    f"Condition '{condition_id}' is used by rule(s): {refs}.\n"
                    "Update or delete those rules first."
                ),
            )
            return

        response = QMessageBox.question(
            self,
            "Delete Condition",
            f"Delete condition '{condition_id}'?\nThis cannot be undone in the current session.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return
        try:
            self.workspace.delete_condition(condition_id)
        except ValueError as exc:
            self._show_user_error("Delete Condition Failed", str(exc))
            return
        self._refresh_project_views()
        self._log(f"Deleted condition: {condition_id}")
        self.statusBar().showMessage(f"Condition '{condition_id}' deleted.")

    def _on_choose_export_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Export Output Folder",
            self.export_output_path.text().strip() or str(Path.cwd()),
        )
        if folder:
            self.export_output_path.setText(folder)

    def _on_export_project(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project JSON file before exporting.",
            )
            return
        output_folder = self.export_output_path.text().strip()
        if not output_folder:
            self._show_user_error(
                "Missing Output Folder",
                "Choose an output folder before exporting.",
            )
            return

        try:
            result = self.workspace.export(output_folder)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self._show_user_error(
                "Export Failed",
                "Could not complete export.",
                str(exc),
            )
            return

        text = [
            "Export completed successfully.",
            f"Output folder: {result['output_folder']}",
            "Generated files:",
        ]
        text.extend(f"- {name}" for name in result["generated_files"])
        self.export_result_output.setPlainText("\n".join(text))
        summary_lines = [
            f"Output folder: {result['output_folder']}",
            "Generated files:",
            *[f"- {name}" for name in result["generated_files"]],
        ]
        self._show_debug_section(
            "Export Output",
            "\n".join(summary_lines),
            payload=result,
        )
        self._switch_to_tab("Debug / Results")
        self._log(f"Export completed: {output_folder}")
        self.statusBar().showMessage("Export completed.")

    def _on_run_simulation(self) -> None:
        if not self.workspace.has_project:
            self._show_user_error(
                "No Project Loaded",
                "Open a project JSON file before running simulation.",
            )
            return
        try:
            seed = parse_seed_text(self.sim_seed_input.text())
        except ValueError:
            self._show_user_error(
                "Invalid Seed",
                "Seed must be blank or an integer value.",
            )
            return

        request = SimulationRequest(
            biome=self.sim_biome_input.text().strip() or "minecraft:forest",
            time=int(self.sim_time_input.value()),
            weather=self.sim_weather_input.currentText().strip() or "clear",
            player_health=int(self.sim_player_health_input.value()),
            is_underwater=self.sim_underwater_input.isChecked(),
            timestamp_ms=int(self.sim_timestamp_input.value()),
            repeat=int(self.sim_repeat_input.value()),
            step_ms=int(self.sim_step_ms_input.value()),
            seed=seed,
        )

        try:
            result = self.workspace.run_simulation(request)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self._show_user_error(
                "Simulation Failed",
                "Could not run simulation for this project/context.",
                str(exc),
            )
            return

        self._show_debug_section(
            "Simulation Output",
            self._format_simulation_summary(result),
            payload=result,
        )
        self._switch_to_tab("Debug / Results")
        self._log(
            "Simulation completed "
            f"(repeat={request.repeat}, timestamp_ms={request.timestamp_ms}, step_ms={request.step_ms})."
        )
        self.statusBar().showMessage("Simulation completed.")

    def _switch_to_tab(self, title: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

    def _show_debug_section(
        self,
        title: str,
        summary_text: str,
        *,
        payload: dict | list | None = None,
    ) -> None:
        lines = [f"=== {title} ===", summary_text.strip()]
        if payload is not None:
            lines.append("")
            lines.append("--- JSON ---")
            lines.append(to_pretty_json(payload))
        self.debug_output.setPlainText("\n".join(lines).strip() + "\n")

    def _format_simulation_summary(self, result: dict) -> str:
        steps = result.get("steps", [])
        if not isinstance(steps, list):
            return "No simulation steps available."
        lines = [f"Timeline steps: {len(steps)}"]
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_index = step.get("step_index", "?")
            timestamp_ms = step.get("timestamp_ms", "?")
            lines.append(f"Step {step_index} @ {timestamp_ms} ms")
            selections = step.get("selections", [])
            if not isinstance(selections, list) or not selections:
                lines.append("  - no selections")
                continue
            for selection in selections:
                if not isinstance(selection, dict):
                    continue
                channel = selection.get("channel", "-")
                rule_id = selection.get("selected_rule_id", "-")
                asset_id = selection.get("selected_asset_id", "-")
                reason = selection.get("reason", "-")
                lines.append(
                    f"  - {channel}: rule={rule_id}, asset={asset_id}, reason={reason}"
                )
        return "\n".join(lines)

    def _update_action_states(self) -> None:
        has_project = self.workspace.has_project
        self.validate_project_button.setEnabled(has_project)
        self.create_condition_button.setEnabled(has_project)
        self.create_rule_button.setEnabled(has_project)
        self.export_button.setEnabled(has_project)
        self.simulate_button.setEnabled(has_project)
        self.save_as_json_button.setEnabled(has_project)
        self.save_as_format_combo.setEnabled(has_project)
        self.conditions_table.setEnabled(has_project)
        self.rules_table.setEnabled(has_project)
        self.assets_table.setEnabled(has_project)

    def _source_format_text(self) -> str:
        if self.workspace.source_format == "legacy_js":
            return "Legacy JS (Imported)"
        if self.workspace.source_format == "js":
            return "JS"
        return "JSON"

    def _show_user_error(
        self, title: str, message: str, details: str | None = None
    ) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        if details:
            dialog.setDetailedText(details)
        dialog.exec()
        self._log(f"{title}: {message}")
        if details:
            self._log(details)

    def _confirm_discard_unsaved_changes(self) -> bool:
        if not self.workspace.is_dirty:
            return True
        response = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them and continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return response == QMessageBox.Yes

    def _update_dirty_state_ui(self) -> None:
        dirty_suffix = " *" if self.workspace.is_dirty else ""
        self.setWindowTitle(f"{self.BASE_TITLE}{dirty_suffix}")
        if self.workspace.project_path:
            path_text = f"Path: {self.workspace.project_path}"
            if self.workspace.is_dirty:
                path_text += " (unsaved changes)"
            self.project_path_label.setText(path_text)
        can_direct_save = (
            self.workspace.has_project
            and self.workspace.is_dirty
            and self.workspace.source_format == "json"
        )
        self.save_project_button.setEnabled(can_direct_save)
        if self.workspace.has_project and self.workspace.source_format != "json":
            self.save_project_button.setToolTip(
                "Direct save to .js is disabled. Use Save As JSON."
            )
        else:
            self.save_project_button.setToolTip("Save project to JSON file.")
        self._update_action_states()

    def _log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def closeEvent(self, event: QCloseEvent) -> None:  # pragma: no cover - UI behavior
        if not self.workspace.is_dirty:
            self.ui_audio_manager.shutdown()
            event.accept()
            return

        response = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before closing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if response == QMessageBox.Save:
            if self._save_current_project(show_success=False):
                self.ui_audio_manager.shutdown()
                event.accept()
            else:
                event.ignore()
            return
        if response == QMessageBox.Discard:
            self.ui_audio_manager.shutdown()
            event.accept()
            return
        event.ignore()

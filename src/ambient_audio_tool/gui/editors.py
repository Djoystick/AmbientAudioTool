from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ambient_audio_tool.models import ConditionExpression, Rule


CHANNEL_VALUES = ["music", "ambient_noise", "context_oneshot", "event_alert"]
TIE_BREAKER_VALUES = ["priority_then_weight", "priority_then_oldest", "stable_rule_id"]


def _error_label() -> QLabel:
    label = QLabel("")
    label.setStyleSheet("color: #b00020;")
    label.setWordWrap(True)
    label.setVisible(False)
    return label


class RuleEditorDialog(QDialog):
    def __init__(
        self,
        *,
        condition_ids: list[str],
        asset_ids: list[str],
        existing_rule_ids: list[str],
        existing_rule: Rule | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Rule" if existing_rule else "Create New Rule")
        self.resize(640, 580)
        self._existing_rule = existing_rule
        self._existing_rule_ids = set(existing_rule_ids)
        self._saved_payload: dict[str, Any] | None = None

        root = QVBoxLayout(self)

        form_box = QGroupBox("Rule Settings")
        form = QFormLayout(form_box)

        self.id_input = QLineEdit(existing_rule.id if existing_rule else "")
        self.id_error = _error_label()

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(CHANNEL_VALUES)

        self.condition_combo = QComboBox()
        self.condition_combo.addItems(condition_ids)
        self.condition_error = _error_label()

        self.base_priority_input = QSpinBox()
        self.base_priority_input.setRange(-10_000, 10_000)
        self.base_priority_input.setValue(
            existing_rule.priority.base_priority if existing_rule else 50
        )

        self.rule_cooldown_input = QSpinBox()
        self.rule_cooldown_input.setRange(0, 86_400_000)
        self.rule_cooldown_input.setValue(
            existing_rule.cooldown.rule_cooldown_ms if existing_rule else 0
        )

        self.asset_cooldown_input = QSpinBox()
        self.asset_cooldown_input.setRange(0, 86_400_000)
        self.asset_cooldown_input.setValue(
            existing_rule.cooldown.asset_cooldown_ms if existing_rule else 0
        )

        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(1.0, 10_000.0)
        self.weight_input.setDecimals(2)
        self.weight_input.setSingleStep(0.25)
        self.weight_input.setValue(
            float(existing_rule.randomness.weight) if existing_rule else 1.0
        )
        self.weight_error = _error_label()

        self.no_repeat_input = QSpinBox()
        self.no_repeat_input.setRange(0, 1000)
        self.no_repeat_input.setValue(
            existing_rule.randomness.no_repeat_window if existing_rule else 0
        )

        self.enabled_input = QCheckBox("Rule enabled")
        self.enabled_input.setChecked(existing_rule.enabled if existing_rule else True)

        self.can_preempt_input = QCheckBox("Can preempt lower priority rule")
        self.can_preempt_input.setChecked(
            existing_rule.conflict.can_preempt_lower_priority if existing_rule else False
        )

        self.max_concurrent_input = QSpinBox()
        self.max_concurrent_input.setRange(1, 8)
        self.max_concurrent_input.setValue(
            existing_rule.conflict.max_concurrent if existing_rule else 1
        )

        self.tie_breaker_combo = QComboBox()
        self.tie_breaker_combo.addItems(TIE_BREAKER_VALUES)

        self.asset_list = QListWidget()
        self.asset_list.setSelectionMode(QListWidget.MultiSelection)
        for asset_id in asset_ids:
            self.asset_list.addItem(QListWidgetItem(asset_id))
        self.asset_error = _error_label()

        if existing_rule:
            self.channel_combo.setCurrentText(existing_rule.channel.value)
            self.condition_combo.setCurrentText(existing_rule.condition_ref)
            self.tie_breaker_combo.setCurrentText(existing_rule.conflict.tie_breaker.value)
            selected_assets = set(existing_rule.asset_ids)
            for index in range(self.asset_list.count()):
                item = self.asset_list.item(index)
                if item.text() in selected_assets:
                    item.setSelected(True)
        else:
            self.tie_breaker_combo.setCurrentText("priority_then_weight")

        form.addRow("Rule ID", self.id_input)
        form.addRow("", self.id_error)
        form.addRow("Channel", self.channel_combo)
        form.addRow("Condition trigger", self.condition_combo)
        form.addRow("", self.condition_error)
        form.addRow("Assets (multi-select)", self.asset_list)
        form.addRow("", self.asset_error)
        form.addRow("Base priority", self.base_priority_input)
        form.addRow("Rule cooldown (ms)", self.rule_cooldown_input)
        form.addRow("Asset cooldown (ms)", self.asset_cooldown_input)
        form.addRow("Randomness weight", self.weight_input)
        form.addRow("", self.weight_error)
        form.addRow("No-repeat window", self.no_repeat_input)
        form.addRow(self.enabled_input)

        conflict_box = QGroupBox("Conflict (Basic)")
        conflict_layout = QFormLayout(conflict_box)
        conflict_layout.addRow("Max concurrent", self.max_concurrent_input)
        conflict_layout.addRow("Tie breaker", self.tie_breaker_combo)
        conflict_layout.addRow(self.can_preempt_input)

        self.form_error = _error_label()

        root.addWidget(form_box)
        root.addWidget(conflict_box)
        root.addWidget(self.form_error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def saved_payload(self) -> dict[str, Any] | None:
        return self._saved_payload

    def _clear_errors(self) -> None:
        for label in (
            self.id_error,
            self.condition_error,
            self.asset_error,
            self.weight_error,
            self.form_error,
        ):
            label.setText("")
            label.setVisible(False)

    def _set_error(self, label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(True)

    def _on_save(self) -> None:
        self._clear_errors()
        rule_id = self.id_input.text().strip()
        selected_assets = [item.text() for item in self.asset_list.selectedItems()]

        has_error = False
        if not rule_id:
            self._set_error(self.id_error, "Rule ID is required.")
            has_error = True
        else:
            is_duplicate = rule_id in self._existing_rule_ids and (
                self._existing_rule is None or rule_id != self._existing_rule.id
            )
            if is_duplicate:
                self._set_error(self.id_error, f"Rule ID '{rule_id}' already exists.")
                has_error = True

        if self.condition_combo.count() == 0:
            self._set_error(
                self.condition_error,
                "No conditions available. Create a condition first.",
            )
            has_error = True

        if not selected_assets:
            self._set_error(self.asset_error, "Select at least one asset.")
            has_error = True

        if self.weight_input.value() < 1:
            self._set_error(self.weight_error, "Weight must be at least 1.")
            has_error = True

        if has_error:
            self._set_error(self.form_error, "Please fix the highlighted fields.")
            return

        existing = self._existing_rule
        payload = {
            "id": rule_id,
            "name": existing.name if existing else None,
            "enabled": self.enabled_input.isChecked(),
            "channel": self.channel_combo.currentText(),
            "condition_ref": self.condition_combo.currentText(),
            "asset_ids": selected_assets,
            "priority": {
                "base_priority": int(self.base_priority_input.value()),
                "contextual_boosts": existing.priority.contextual_boosts if existing else {},
                "suppression_threshold": (
                    existing.priority.suppression_threshold if existing else 0
                ),
            },
            "randomness": {
                "probability": float(existing.randomness.probability) if existing else 1.0,
                "weight": max(1, int(round(self.weight_input.value()))),
                "no_repeat_window": int(self.no_repeat_input.value()),
                "jitter_ms": int(existing.randomness.jitter_ms) if existing else 0,
                "rotation_pool": existing.randomness.rotation_pool if existing else None,
            },
            "cooldown": {
                "rule_cooldown_ms": int(self.rule_cooldown_input.value()),
                "asset_cooldown_ms": int(self.asset_cooldown_input.value()),
                "min_delay_ms": int(existing.cooldown.min_delay_ms) if existing else 0,
                "max_delay_ms": int(existing.cooldown.max_delay_ms) if existing else 0,
            },
            "conflict": {
                "scope": existing.conflict.scope.value if existing else "channel",
                "max_concurrent": int(self.max_concurrent_input.value()),
                "tie_breaker": self.tie_breaker_combo.currentText(),
                "can_preempt_lower_priority": self.can_preempt_input.isChecked(),
            },
        }

        try:
            Rule.model_validate(payload)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            location = ".".join(str(part) for part in first_error.get("loc", []))
            message = first_error.get("msg", "Invalid rule.")
            self._set_error(
                self.form_error,
                f"Invalid field '{location}': {message}" if location else message,
            )
            return

        self._saved_payload = payload
        self.accept()


class _PredicateRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.field_combo = QComboBox()
        self.field_combo.addItems(["biome", "time", "weather", "player_health", "underwater"])
        self.operator_combo = QComboBox()
        self.value_input = QLineEdit()

        layout.addWidget(QLabel("Field"), 0, 0)
        layout.addWidget(self.field_combo, 0, 1)
        layout.addWidget(QLabel("Operator"), 0, 2)
        layout.addWidget(self.operator_combo, 0, 3)
        layout.addWidget(QLabel("Value"), 0, 4)
        layout.addWidget(self.value_input, 0, 5)

        self.field_combo.currentTextChanged.connect(self._refresh_operator_options)
        self._refresh_operator_options(self.field_combo.currentText())

    def _refresh_operator_options(self, field_name: str) -> None:
        self.operator_combo.clear()
        if field_name in {"biome", "weather"}:
            self.operator_combo.addItems(["="])
            self.value_input.setPlaceholderText("Value")
            self.value_input.setEnabled(True)
            return
        if field_name in {"time", "player_health"}:
            self.operator_combo.addItems(["between", "=", ">=", "<="])
            if field_name == "time":
                self.value_input.setPlaceholderText("between: 6-17, or single number")
            else:
                self.value_input.setPlaceholderText("between: 0-10, or single number")
            self.value_input.setEnabled(True)
            return
        self.operator_combo.addItems(["is_true", "is_false"])
        self.value_input.setPlaceholderText("Not used for underwater")
        self.value_input.setEnabled(False)

    def to_predicate(self) -> dict[str, Any]:
        field_name = self.field_combo.currentText()
        operator = self.operator_combo.currentText()
        value_raw = self.value_input.text().strip()
        if field_name == "biome":
            if not value_raw:
                raise ValueError("Biome value is required.")
            return {"type": "biome_is", "biome": value_raw}
        if field_name == "weather":
            weather = value_raw.lower()
            if weather not in {"clear", "rain", "thunder", "snow"}:
                raise ValueError("Weather must be one of: clear, rain, thunder, snow.")
            return {"type": "weather_is", "weather": weather}
        if field_name == "time":
            start_hour, end_hour = _parse_range_or_single(value_raw, operator, as_int=True)
            return {"type": "time_between", "start_hour": int(start_hour), "end_hour": int(end_hour)}
        if field_name == "player_health":
            min_health, max_health = _parse_range_or_single(value_raw, operator, as_int=False)
            return {
                "type": "player_health_range",
                "min_health": float(min_health),
                "max_health": float(max_health),
            }
        return {"type": "is_underwater", "value": operator == "is_true"}

    def load_predicate(self, predicate: dict[str, Any]) -> None:
        predicate_type = predicate.get("type")
        if predicate_type == "biome_is":
            self.field_combo.setCurrentText("biome")
            self.operator_combo.setCurrentText("=")
            self.value_input.setText(str(predicate.get("biome", "")))
            return
        if predicate_type == "weather_is":
            self.field_combo.setCurrentText("weather")
            self.operator_combo.setCurrentText("=")
            self.value_input.setText(str(predicate.get("weather", "")))
            return
        if predicate_type == "time_between":
            self.field_combo.setCurrentText("time")
            self.operator_combo.setCurrentText("between")
            self.value_input.setText(
                f"{predicate.get('start_hour', 0)}-{predicate.get('end_hour', 0)}"
            )
            return
        if predicate_type == "player_health_range":
            self.field_combo.setCurrentText("player_health")
            self.operator_combo.setCurrentText("between")
            self.value_input.setText(
                f"{predicate.get('min_health', 0)}-{predicate.get('max_health', 0)}"
            )
            return
        if predicate_type == "is_underwater":
            self.field_combo.setCurrentText("underwater")
            value = bool(predicate.get("value", True))
            self.operator_combo.setCurrentText("is_true" if value else "is_false")


def _parse_range_or_single(
    value_raw: str,
    operator: str,
    *,
    as_int: bool,
) -> tuple[int | float, int | float]:
    parser = int if as_int else float
    if operator == "between":
        if "-" not in value_raw:
            raise ValueError("Range value must use 'min-max' format.")
        left, right = (part.strip() for part in value_raw.split("-", 1))
        start = parser(left)
        end = parser(right)
        if end < start:
            raise ValueError("Range end must be greater than or equal to start.")
        return start, end

    value = parser(value_raw)
    if operator == "=":
        return value, value
    if operator == ">=":
        return value, 23 if as_int else 100.0
    if operator == "<=":
        return 0 if as_int else 0.0, value
    raise ValueError(f"Unsupported operator '{operator}'.")


class ConditionEditorDialog(QDialog):
    def __init__(
        self,
        *,
        existing_condition_ids: list[str],
        existing_condition: ConditionExpression | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            "Edit Condition" if existing_condition is not None else "Create New Condition"
        )
        self.resize(760, 660)
        self._existing_condition = existing_condition
        self._existing_condition_ids = set(existing_condition_ids)
        self._saved_payload: dict[str, Any] | None = None

        root = QVBoxLayout(self)

        header = QFormLayout()
        self.id_input = QLineEdit(existing_condition.id if existing_condition else "")
        self.id_error = _error_label()
        header.addRow("Condition ID", self.id_input)
        header.addRow("", self.id_error)
        root.addLayout(header)

        self.advanced_mode = QCheckBox("Advanced JSON mode")
        self.advanced_mode.setChecked(False)
        root.addWidget(self.advanced_mode)

        self.simple_panel = QWidget()
        simple_layout = QVBoxLayout(self.simple_panel)
        simple_form = QFormLayout()
        self.root_op_combo = QComboBox()
        self.root_op_combo.addItems(["AND", "OR", "NOT"])
        simple_form.addRow("Root operation", self.root_op_combo)
        simple_layout.addLayout(simple_form)

        self.row_one = _PredicateRow(self)
        self.row_two = _PredicateRow(self)
        self.row_two_title = QLabel("Predicate 2 (required for AND/OR)")
        simple_layout.addWidget(QLabel("Predicate 1"))
        simple_layout.addWidget(self.row_one)
        simple_layout.addWidget(self.row_two_title)
        simple_layout.addWidget(self.row_two)
        self.simple_error = _error_label()
        simple_layout.addWidget(self.simple_error)

        self.advanced_panel = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.addWidget(QLabel("Condition root JSON (advanced):"))
        self.advanced_json_input = QPlainTextEdit()
        advanced_layout.addWidget(self.advanced_json_input)
        self.json_error = _error_label()
        advanced_layout.addWidget(self.json_error)

        self.form_error = _error_label()

        root.addWidget(self.simple_panel)
        root.addWidget(self.advanced_panel)
        root.addWidget(self.form_error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.advanced_mode.toggled.connect(self._update_mode_visibility)
        self.root_op_combo.currentTextChanged.connect(self._on_root_op_changed)
        self._on_root_op_changed(self.root_op_combo.currentText())

        if existing_condition is not None:
            self._load_condition(existing_condition)
        else:
            self._update_mode_visibility(False)

    @property
    def saved_payload(self) -> dict[str, Any] | None:
        return self._saved_payload

    def _clear_errors(self) -> None:
        for label in (
            self.id_error,
            self.simple_error,
            self.json_error,
            self.form_error,
        ):
            label.setText("")
            label.setVisible(False)

    def _set_error(self, label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(True)

    def _on_root_op_changed(self, op_text: str) -> None:
        is_not = op_text == "NOT"
        self.row_two.setVisible(not is_not)
        self.row_two_title.setVisible(not is_not)

    def _update_mode_visibility(self, advanced: bool) -> None:
        self.simple_panel.setVisible(not advanced)
        self.advanced_panel.setVisible(advanced)

    def _load_condition(self, condition: ConditionExpression) -> None:
        root_payload = condition.root.model_dump(mode="json")
        self.advanced_json_input.setPlainText(
            json.dumps(root_payload, indent=2, ensure_ascii=False)
        )

        if self._try_load_simple_mode(root_payload):
            self.advanced_mode.setChecked(False)
        else:
            self.advanced_mode.setChecked(True)
        self._update_mode_visibility(self.advanced_mode.isChecked())

    def _try_load_simple_mode(self, root_payload: dict[str, Any]) -> bool:
        op = root_payload.get("op")
        if op in {"ALL", "ANY"}:
            nodes = root_payload.get("nodes", [])
            if (
                isinstance(nodes, list)
                and len(nodes) == 2
                and all(isinstance(node, dict) and node.get("op") == "PRED" for node in nodes)
            ):
                self.root_op_combo.setCurrentText("AND" if op == "ALL" else "OR")
                self.row_one.load_predicate(nodes[0].get("predicate", {}))
                self.row_two.load_predicate(nodes[1].get("predicate", {}))
                return True
            return False

        if op == "NOT":
            node = root_payload.get("node")
            if isinstance(node, dict) and node.get("op") == "PRED":
                self.root_op_combo.setCurrentText("NOT")
                self.row_one.load_predicate(node.get("predicate", {}))
                return True
            return False
        return False

    def _on_save(self) -> None:
        self._clear_errors()
        condition_id = self.id_input.text().strip()

        has_error = False
        if not condition_id:
            self._set_error(self.id_error, "Condition ID is required.")
            has_error = True
        else:
            is_duplicate = condition_id in self._existing_condition_ids and (
                self._existing_condition is None
                or condition_id != self._existing_condition.id
            )
            if is_duplicate:
                self._set_error(
                    self.id_error, f"Condition ID '{condition_id}' already exists."
                )
                has_error = True

        if has_error:
            self._set_error(self.form_error, "Please fix the highlighted fields.")
            return

        try:
            if self.advanced_mode.isChecked():
                root = json.loads(self.advanced_json_input.toPlainText() or "{}")
                if not isinstance(root, dict):
                    raise ValueError("Root JSON must be an object.")
            else:
                root = self._build_simple_root()
            existing = self._existing_condition
            payload = {
                "id": condition_id,
                "name": existing.name if existing else None,
                "root": root,
            }
            ConditionExpression.model_validate(payload)
            self._saved_payload = payload
            self.accept()
        except json.JSONDecodeError as exc:
            self._set_error(self.json_error, f"Invalid JSON: {exc.msg}")
            self._set_error(self.form_error, "Please fix the highlighted fields.")
        except ValueError as exc:
            target = self.json_error if self.advanced_mode.isChecked() else self.simple_error
            self._set_error(target, str(exc))
            self._set_error(self.form_error, "Please fix the highlighted fields.")
        except ValidationError as exc:
            first_error = exc.errors()[0]
            location = ".".join(str(part) for part in first_error.get("loc", []))
            message = first_error.get("msg", "Invalid condition.")
            target = self.json_error if self.advanced_mode.isChecked() else self.simple_error
            self._set_error(
                target,
                f"Invalid field '{location}': {message}" if location else message,
            )
            self._set_error(self.form_error, "Please fix the highlighted fields.")

    def _build_simple_root(self) -> dict[str, Any]:
        op_text = self.root_op_combo.currentText()
        first_predicate = {"op": "PRED", "predicate": self.row_one.to_predicate()}
        if op_text == "NOT":
            return {"op": "NOT", "node": first_predicate}
        second_predicate = {"op": "PRED", "predicate": self.row_two.to_predicate()}
        root_op = "ALL" if op_text == "AND" else "ANY"
        return {"op": root_op, "nodes": [first_predicate, second_predicate]}

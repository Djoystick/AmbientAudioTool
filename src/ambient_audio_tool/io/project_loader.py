from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .legacy_ambient_importer import import_ambient_config


@dataclass(frozen=True)
class ProjectLoadError(Exception):
    message: str
    location: str = ""
    code: str = "invalid_project_source"

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class LoadedProjectSource:
    payload: dict[str, Any]
    source_format: str
    warnings: list[str]
    source_note: str = ""


def load_project_data(path: str | Path) -> tuple[dict[str, Any], str]:
    loaded = load_project_source(path)
    return loaded.payload, loaded.source_format


def load_project_source(path: str | Path) -> LoadedProjectSource:
    file_path = Path(path)
    if not file_path.exists():
        raise ProjectLoadError(
            message=f"Project file does not exist: {file_path}",
            location=str(file_path),
            code="file_not_found",
        )

    suffix = file_path.suffix.lower()
    raw_text = file_path.read_text(encoding="utf-8")

    if suffix == ".json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ProjectLoadError(
                message=f"JSON parse error: {exc.msg}",
                location=f"{file_path}:{exc.lineno}:{exc.colno}",
                code="invalid_json",
            ) from exc
        if not isinstance(payload, dict):
            raise ProjectLoadError(
                message="Project root must be a JSON object.",
                location=str(file_path),
            )
        return LoadedProjectSource(
            payload=payload,
            source_format="json",
            warnings=[],
        )

    if suffix == ".js":
        legacy_wrapper = re.compile(r"^\s*export\s+const\s+AMBIENT_CONFIG\s*=\s*", re.DOTALL)
        legacy_match = legacy_wrapper.match(raw_text)
        if legacy_match:
            legacy_literal, end_index = _extract_balanced_object(
                raw_text, legacy_match.end(), str(file_path)
            )
            if not _is_trailing_js_terminator(raw_text[end_index:]):
                raise ProjectLoadError(
                    message=(
                        "Unsupported JavaScript content after AMBIENT_CONFIG object. "
                        "Only a single exported object is allowed."
                    ),
                    location=str(file_path),
                )
            parser = _JsDataParser(legacy_literal, str(file_path))
            legacy_config = parser.parse_root_value()
            if not isinstance(legacy_config, dict):
                raise ProjectLoadError(
                    message="AMBIENT_CONFIG must be an object literal.",
                    location=str(file_path),
                )
            import_result = import_ambient_config(
                legacy_config,
                source_path=file_path,
            )
            return LoadedProjectSource(
                payload=import_result.project_payload,
                source_format="legacy_js",
                warnings=import_result.warnings,
                source_note="Imported from legacy AMBIENT_CONFIG JS format.",
            )

        payload = _parse_js_project_source(raw_text, str(file_path))
        return LoadedProjectSource(
            payload=payload,
            source_format="js",
            warnings=[],
        )

    raise ProjectLoadError(
        message=(
            f"Unsupported project file extension '{suffix or '(none)'}'. "
            "Supported: .json, .js"
        ),
        location=str(file_path),
        code="unsupported_extension",
    )


def _parse_js_project_source(source_text: str, location_hint: str) -> dict[str, Any]:
    literal_text = _extract_supported_js_object_literal(source_text, location_hint)
    parser = _JsDataParser(literal_text, location_hint)
    value = parser.parse_root_value()
    if not isinstance(value, dict):
        raise ProjectLoadError(
            message="JavaScript project payload must be an object literal.",
            location=location_hint,
        )
    return value


def _extract_supported_js_object_literal(source_text: str, location_hint: str) -> str:
    wrappers = [
        re.compile(r"^\s*module\.exports\s*=\s*", re.DOTALL),
        re.compile(r"^\s*export\s+default\s+", re.DOTALL),
        re.compile(r"^\s*export\s+const\s+project\s*=\s*", re.DOTALL),
        re.compile(r"^\s*export\s+const\s+PROJECT\s*=\s*", re.DOTALL),
    ]
    for wrapper in wrappers:
        match = wrapper.match(source_text)
        if not match:
            continue
        literal_text, end_index = _extract_balanced_object(source_text, match.end(), location_hint)
        if not _is_trailing_js_terminator(source_text[end_index:]):
            raise ProjectLoadError(
                message=(
                    "Unsupported JavaScript content after exported object. "
                    "Only a single exported object is allowed."
                ),
                location=location_hint,
            )
        return literal_text

    raise ProjectLoadError(
        message=(
            "Unsupported JavaScript project format. Supported forms are:\n"
            "1) module.exports = { ... }\n"
            "2) export default { ... }\n"
            "3) export const project = { ... }\n"
            "4) export const PROJECT = { ... }\n"
            "5) export const AMBIENT_CONFIG = { ... }"
        ),
        location=location_hint,
    )


def _extract_balanced_object(
    source_text: str, start_index: int, location_hint: str
) -> tuple[str, int]:
    index = start_index
    length = len(source_text)
    while index < length and source_text[index].isspace():
        index += 1
    if index >= length or source_text[index] != "{":
        raise ProjectLoadError(
            message="Expected object literal after export wrapper.",
            location=location_hint,
        )

    depth = 0
    in_string: str | None = None
    escaped = False
    i = index
    while i < length:
        ch = source_text[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in {'"', "'"}:
            in_string = ch
            i += 1
            continue
        if ch == "`":
            raise ProjectLoadError(
                message="Template strings are not supported in JS project files.",
                location=location_hint,
            )
        if ch == "/" and i + 1 < length and source_text[i + 1] == "/":
            i = _skip_line_comment(source_text, i + 2)
            continue
        if ch == "/" and i + 1 < length and source_text[i + 1] == "*":
            i = _skip_block_comment(source_text, i + 2, location_hint)
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source_text[index : i + 1], i + 1
        i += 1

    raise ProjectLoadError(
        message="Could not find a complete object literal in JS project file.",
        location=location_hint,
    )


def _is_trailing_js_terminator(text: str) -> bool:
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace() or ch == ";":
            i += 1
            continue
        if ch == "/" and i + 1 < length and text[i + 1] == "/":
            i = _skip_line_comment(text, i + 2)
            continue
        if ch == "/" and i + 1 < length and text[i + 1] == "*":
            i = _skip_block_comment(text, i + 2, "trailing content")
            continue
        return False
    return True


def _skip_line_comment(text: str, start: int) -> int:
    i = start
    while i < len(text) and text[i] not in "\r\n":
        i += 1
    return i


def _skip_block_comment(text: str, start: int, location_hint: str) -> int:
    i = start
    while i + 1 < len(text):
        if text[i] == "*" and text[i + 1] == "/":
            return i + 2
        i += 1
    raise ProjectLoadError(
        message="Unclosed block comment in JS project file.",
        location=location_hint,
    )


class _JsDataParser:
    NUMBER_PATTERN = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")

    def __init__(self, text: str, location_hint: str) -> None:
        self.text = text
        self.location_hint = location_hint
        self.index = 0

    def parse_root_value(self) -> Any:
        self._skip_ws_comments()
        value = self._parse_value()
        self._skip_ws_comments()
        if self.index != len(self.text):
            self._error("Unexpected trailing content in JS object literal.")
        return value

    def _parse_value(self) -> Any:
        self._skip_ws_comments()
        if self.index >= len(self.text):
            self._error("Unexpected end of JS data.")
        ch = self.text[self.index]
        if ch == "{":
            return self._parse_object()
        if ch == "[":
            return self._parse_array()
        if ch in {'"', "'"}:
            return self._parse_string()
        if ch == "-" or ch.isdigit():
            return self._parse_number()
        if self.text.startswith("true", self.index):
            self.index += 4
            return True
        if self.text.startswith("false", self.index):
            self.index += 5
            return False
        if self.text.startswith("null", self.index):
            self.index += 4
            return None
        if ch == "`":
            self._error("Template strings are not supported.")
        identifier = self._parse_identifier(allow_failure=True)
        if identifier:
            self._error(
                f"Unsupported identifier '{identifier}'. "
                "Only true/false/null literals are allowed."
            )
        self._error(f"Unsupported token '{ch}'.")
        return None

    def _parse_object(self) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        self._expect("{")
        self._skip_ws_comments()
        if self._peek("}"):
            self.index += 1
            return obj

        while True:
            key = self._parse_object_key()
            self._skip_ws_comments()
            self._expect(":")
            value = self._parse_value()
            obj[key] = value
            self._skip_ws_comments()
            if self._peek(","):
                self.index += 1
                self._skip_ws_comments()
                if self._peek("}"):
                    self.index += 1
                    return obj
                continue
            self._expect("}")
            return obj

    def _parse_object_key(self) -> str:
        self._skip_ws_comments()
        if self.index >= len(self.text):
            self._error("Unexpected end while parsing object key.")
        ch = self.text[self.index]
        if ch in {'"', "'"}:
            key = self._parse_string()
            if not isinstance(key, str):
                self._error("Object key must be a string.")
            return key
        if ch == "[":
            self._error("Computed object keys are not supported.")
        identifier = self._parse_identifier(allow_failure=False)
        return identifier

    def _parse_array(self) -> list[Any]:
        items: list[Any] = []
        self._expect("[")
        self._skip_ws_comments()
        if self._peek("]"):
            self.index += 1
            return items

        while True:
            items.append(self._parse_value())
            self._skip_ws_comments()
            if self._peek(","):
                self.index += 1
                self._skip_ws_comments()
                if self._peek("]"):
                    self.index += 1
                    return items
                continue
            self._expect("]")
            return items

    def _parse_string(self) -> str:
        quote = self.text[self.index]
        self.index += 1
        chars: list[str] = []
        while self.index < len(self.text):
            ch = self.text[self.index]
            self.index += 1
            if ch == quote:
                return "".join(chars)
            if ch == "\\":
                if self.index >= len(self.text):
                    self._error("Incomplete escape sequence in string.")
                esc = self.text[self.index]
                self.index += 1
                if esc in {'"', "'", "\\", "/"}:
                    chars.append(esc)
                    continue
                if esc == "b":
                    chars.append("\b")
                    continue
                if esc == "f":
                    chars.append("\f")
                    continue
                if esc == "n":
                    chars.append("\n")
                    continue
                if esc == "r":
                    chars.append("\r")
                    continue
                if esc == "t":
                    chars.append("\t")
                    continue
                if esc == "u":
                    if self.index + 4 > len(self.text):
                        self._error("Incomplete unicode escape sequence.")
                    hex_chars = self.text[self.index : self.index + 4]
                    if not re.fullmatch(r"[0-9a-fA-F]{4}", hex_chars):
                        self._error("Invalid unicode escape sequence.")
                    chars.append(chr(int(hex_chars, 16)))
                    self.index += 4
                    continue
                self._error(f"Unsupported string escape '\\{esc}'.")
            else:
                chars.append(ch)
        self._error("Unterminated string literal.")
        return ""

    def _parse_number(self) -> int | float:
        match = self.NUMBER_PATTERN.match(self.text, self.index)
        if not match:
            self._error("Invalid number literal.")
        raw = match.group(0)
        self.index = match.end()
        if any(ch in raw for ch in ".eE"):
            return float(raw)
        return int(raw)

    def _parse_identifier(self, *, allow_failure: bool) -> str:
        if self.index >= len(self.text):
            if allow_failure:
                return ""
            self._error("Expected identifier.")

        first = self.text[self.index]
        if not (first.isalpha() or first in {"_", "$"}):
            if allow_failure:
                return ""
            self._error("Expected identifier.")

        start = self.index
        self.index += 1
        while self.index < len(self.text):
            ch = self.text[self.index]
            if ch.isalnum() or ch in {"_", "$"}:
                self.index += 1
                continue
            break
        return self.text[start : self.index]

    def _skip_ws_comments(self) -> None:
        while self.index < len(self.text):
            ch = self.text[self.index]
            if ch.isspace():
                self.index += 1
                continue
            if ch == "/" and self.index + 1 < len(self.text):
                nxt = self.text[self.index + 1]
                if nxt == "/":
                    self.index = _skip_line_comment(self.text, self.index + 2)
                    continue
                if nxt == "*":
                    self.index = _skip_block_comment(
                        self.text, self.index + 2, self.location_hint
                    )
                    continue
            break

    def _peek(self, token: str) -> bool:
        return self.text.startswith(token, self.index)

    def _expect(self, token: str) -> None:
        if not self._peek(token):
            found = self.text[self.index] if self.index < len(self.text) else "end of input"
            self._error(f"Expected '{token}' but found '{found}'.")
        self.index += len(token)

    def _error(self, message: str) -> None:
        pointer = self.index + 1
        raise ProjectLoadError(
            message=f"{message} (at character {pointer}).",
            location=self.location_hint,
        )

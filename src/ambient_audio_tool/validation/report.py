from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    location: str = ""

    def to_line(self) -> str:
        loc = f" [{self.location}]" if self.location else ""
        return f"{self.severity.upper()} {self.code}{loc}: {self.message}"


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                location=location,
            )
        )

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.WARNING)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def to_text(self) -> str:
        if not self.issues:
            return "Validation succeeded. No issues found."
        lines = ["Validation completed with issues:"]
        for issue in self.issues:
            lines.append(f"- {issue.to_line()}")
        lines.append(
            f"Summary: {self.error_count} error(s), {self.warning_count} warning(s)."
        )
        return "\n".join(lines)

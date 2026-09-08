import re
from typing import ClassVar

from pydantic import BaseModel


class IntegrationTestsStats(BaseModel):
    """Numbers parsed from a raw test log of an IntegrationTests result"""

    # counts of the pytest summary like "1 failed, 12 passed, 3 warnings"
    PYTEST_OUTCOME_PATTERN: ClassVar[re.Pattern] = re.compile(
        r"(\d+)\s+([a-z]+)"
    )

    # duration of the pytest summary like "in 174.21s (0:02:54)"
    PYTEST_DURATION_PATTERN: ClassVar[re.Pattern] = re.compile(
        r"\bin\s+([\d.]+)s"
    )

    # collection of the pytest log like "collected 241 items"
    PYTEST_COLLECTED_PATTERN: ClassVar[re.Pattern] = re.compile(
        r"collected\s+(\d+)\s+items?"
    )

    # a part of the pytest counts is named in plural
    PYTEST_OUTCOME_ALIASES: ClassVar[dict[str, str]] = {
        "errors": "error",
        "warnings": "warning",
    }

    # counts of the short form, shown even when they are zero
    ALWAYS_SHOWN_COUNTS: ClassVar[tuple[str, ...]] = (
        "passed",
        "skipped",
        "failed",
        "error",
    )

    # counts of the short form, shown only when pytest reports them
    OPTIONALLY_SHOWN_COUNTS: ClassVar[tuple[str, ...]] = (
        "xfailed",
        "xpassed",
        "deselected",
        "warning",
    )

    # one Telegram message can not be longer than 4096 characters
    MAX_TELEGRAM_RESULT_LENGTH: ClassVar[int] = 256

    collected: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    xfailed: int = 0
    xpassed: int = 0
    deselected: int = 0
    warning: int = 0
    duration: float | None = None

    @classmethod
    def get_summary(cls, result: str | None) -> str | None:
        """pytest closes a log with a summary line framed by "=" """
        if not result:
            return None

        for line in reversed(result.splitlines()):
            stripped = line.strip()
            if stripped.startswith("=") and " in " in stripped:
                return stripped.strip("=").strip()

        return None

    @classmethod
    def from_result(cls, result: str | None) -> IntegrationTestsStats:
        summary = cls.get_summary(result)
        if not summary:
            return cls()

        counts = {}
        for count, outcome in cls.PYTEST_OUTCOME_PATTERN.findall(summary):
            name = cls.PYTEST_OUTCOME_ALIASES.get(outcome, outcome)
            if name in cls.ALWAYS_SHOWN_COUNTS + cls.OPTIONALLY_SHOWN_COUNTS:
                counts[name] = counts.get(name, 0) + int(count)

        collected = cls.PYTEST_COLLECTED_PATTERN.search(result)
        duration = cls.PYTEST_DURATION_PATTERN.search(summary)

        return cls(
            **counts,
            collected=int(collected.group(1)) if collected else 0,
            duration=float(duration.group(1)) if duration else None,
        )

    @property
    def total(self) -> int:
        """All tests taken into the run, the skipped ones included"""
        if self.collected:
            return self.collected - self.deselected

        # pytest prints no collection line in the quiet mode
        return (
            self.passed
            + self.failed
            + self.error
            + self.skipped
            + self.xfailed
            + self.xpassed
        )

    @property
    def executed(self) -> int:
        return self.total - self.skipped

    @property
    def success(self) -> int:
        return self.passed + self.xpassed

    @property
    def success_percentage(self) -> float | None:
        if not self.executed:
            return None

        return round(self.success / self.executed * 100, 2)

    def to_text(self) -> str | None:
        """Short form like "total 241, passed 231, failed 0 in 174.21s" """
        if not self.total and self.duration is None:
            return None

        counts = [f"total {self.total}"]
        counts += [
            f"{name} {getattr(self, name)}"
            for name in self.ALWAYS_SHOWN_COUNTS
        ]
        counts += [
            f"{name} {getattr(self, name)}"
            for name in self.OPTIONALLY_SHOWN_COUNTS
            if getattr(self, name)
        ]

        text = ", ".join(counts)
        if self.duration is None:
            return text

        return f"{text} in {self.duration:.2f}s"

    @classmethod
    def get_result_text(cls, result: str) -> str:
        """A full test log is useless in Telegram, its counts are enough

        A result without the pytest summary line is shown by its tail
        """
        return (
            cls.from_result(result).to_text()
            or result[-cls.MAX_TELEGRAM_RESULT_LENGTH :]
        )

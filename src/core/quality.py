"""
Reusable data quality checking framework.

Provides a structured way to assess and report on data quality issues
commonly found in retail data. Designed to be extended for specific
client requirements.
"""

from dataclasses import dataclass, field
from typing import Callable, Any
import pandas as pd


@dataclass
class DataQualityIssue:
    """A single data quality issue found in the data."""

    column: str
    issue_type: str  # e.g., "missing", "invalid_format", "outlier", "duplicate"
    severity: str  # "critical", "warning", "info"
    count: int
    percentage: float
    sample_values: list[Any] = field(default_factory=list)
    description: str = ""


@dataclass
class DataQualityReport:
    """Summary report of data quality for a single data source."""

    source_name: str
    total_rows: int
    issues: list[DataQualityIssue] = field(default_factory=list)

    @property
    def critical_issues(self) -> list[DataQualityIssue]:
        return [i for i in self.issues if i.severity == "critical"]

    @property
    def warning_issues(self) -> list[DataQualityIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def has_critical_issues(self) -> bool:
        return len(self.critical_issues) > 0

    def summary(self) -> dict:
        """Return a summary dict for display."""
        return {
            "source": self.source_name,
            "total_rows": self.total_rows,
            "critical": len(self.critical_issues),
            "warnings": len(self.warning_issues),
            "info": len([i for i in self.issues if i.severity == "info"]),
        }


class DataQualityChecker:
    """
    Reusable data quality checker for retail data.

    Checks for common issues:
    - Missing values
    - Invalid/unparseable values
    - Outliers
    - Duplicates

    Extend by adding custom checks via add_check().
    """

    def __init__(self, source_name: str):
        self.source_name = source_name
        self._checks: list[Callable[[pd.DataFrame], list[DataQualityIssue]]] = []
        self._add_default_checks()

    def _add_default_checks(self):
        """Add default quality checks."""
        self.add_check(self._check_missing_values)

    def add_check(
        self, check_fn: Callable[[pd.DataFrame], list[DataQualityIssue]]
    ) -> "DataQualityChecker":
        """Add a custom check function. Returns self for chaining."""
        self._checks.append(check_fn)
        return self

    def _check_missing_values(self, df: pd.DataFrame) -> list[DataQualityIssue]:
        """Check for missing values in all columns."""
        issues = []
        for col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                pct = (missing / len(df)) * 100
                severity = "critical" if pct > 20 else "warning" if pct > 5 else "info"
                issues.append(
                    DataQualityIssue(
                        column=col,
                        issue_type="missing",
                        severity=severity,
                        count=missing,
                        percentage=pct,
                        description=f"{missing:,} missing values ({pct:.1f}%)",
                    )
                )
        return issues

    def check_duplicates(
        self, key_columns: list[str], severity: str = "warning"
    ) -> "DataQualityChecker":
        """Add a duplicate check for the given columns."""

        def check(df: pd.DataFrame) -> list[DataQualityIssue]:
            dupes = df.duplicated(subset=key_columns, keep=False).sum()
            if dupes > 0:
                return [
                    DataQualityIssue(
                        column=", ".join(key_columns),
                        issue_type="duplicate",
                        severity=severity,
                        count=dupes,
                        percentage=(dupes / len(df)) * 100,
                        description=f"{dupes:,} duplicate rows on key columns",
                    )
                ]
            return []

        self._checks.append(check)
        return self

    def check_invalid_values(
        self,
        column: str,
        valid_values: set | None = None,
        validator: Callable[[Any], bool] | None = None,
        severity: str = "warning",
    ) -> "DataQualityChecker":
        """Add a check for invalid values in a column."""

        def check(df: pd.DataFrame) -> list[DataQualityIssue]:
            if column not in df.columns:
                return []

            if valid_values:
                # Normalize comparison for case-insensitive matching if strings
                col_values = df[column].dropna()
                if col_values.dtype == object:
                    invalid_mask = ~col_values.str.upper().isin(
                        {str(v).upper() for v in valid_values}
                    )
                else:
                    invalid_mask = ~col_values.isin(valid_values)
                invalid = invalid_mask.sum()
                samples = col_values[invalid_mask].head(5).tolist()
            elif validator:
                mask = df[column].dropna().apply(lambda x: not validator(x))
                invalid = mask.sum()
                samples = df.loc[mask[mask].index, column].head(5).tolist()
            else:
                return []

            if invalid > 0:
                return [
                    DataQualityIssue(
                        column=column,
                        issue_type="invalid_format",
                        severity=severity,
                        count=invalid,
                        percentage=(invalid / len(df)) * 100,
                        sample_values=samples,
                        description=f"{invalid:,} invalid values",
                    )
                ]
            return []

        self._checks.append(check)
        return self

    def check_outliers(
        self,
        column: str,
        min_val: float | None = None,
        max_val: float | None = None,
        severity: str = "warning",
    ) -> "DataQualityChecker":
        """Add a check for outlier values outside min/max bounds."""

        def check(df: pd.DataFrame) -> list[DataQualityIssue]:
            if column not in df.columns:
                return []

            values = pd.to_numeric(df[column], errors="coerce")
            outlier_mask = pd.Series([False] * len(values))

            if min_val is not None:
                outlier_mask |= values < min_val
            if max_val is not None:
                outlier_mask |= values > max_val

            outliers = outlier_mask.sum()
            if outliers > 0:
                samples = df.loc[outlier_mask, column].head(5).tolist()
                return [
                    DataQualityIssue(
                        column=column,
                        issue_type="outlier",
                        severity=severity,
                        count=outliers,
                        percentage=(outliers / len(df)) * 100,
                        sample_values=samples,
                        description=f"{outliers:,} values outside expected range",
                    )
                ]
            return []

        self._checks.append(check)
        return self

    def run(self, df: pd.DataFrame) -> DataQualityReport:
        """Run all checks and return a quality report."""
        all_issues = []
        for check_fn in self._checks:
            all_issues.extend(check_fn(df))

        return DataQualityReport(
            source_name=self.source_name, total_rows=len(df), issues=all_issues
        )

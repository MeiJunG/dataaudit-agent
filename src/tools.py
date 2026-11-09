"""Data quality tools. All reported statistics are computed from the active frame."""

from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
import pandas as pd
from langchain_core.tools import StructuredTool
from .value_hints import value_hints

SENSITIVE_NAME_PARTS = {"id", "name", "email", "phone", "address", "ssn", "social", "birth", "dob", "salary", "income", "account", "token", "secret", "credit", "card"}
SENSITIVE_CHINESE_PARTS = {'姓名','联系人','手机','电话','邮箱','地址','身份证','证件','银行卡','账号','密码','密钥','工资','薪资','出生','编号','学号','工号'}


def is_sensitive_column(column: Any) -> bool:
    label = str(column).casefold()
    parts = set(re.split(r"[^a-z0-9]+", label))
    return bool(parts & SENSITIVE_NAME_PARTS) or label.endswith("id") or any(p in label for p in SENSITIVE_CHINESE_PARTS)


_is_sensitive = is_sensitive_column


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)


def build_tools(frame: pd.DataFrame, reference_frame=None) -> list[StructuredTool]:
    # Keep the frame private to this invocation; arguments cannot choose a file/path.
    def inspect_schema() -> str:
        columns = []
        for name in frame.columns:
            series = frame[name]
            examples = [] if _is_sensitive(name) else series.dropna().astype(str).head(3).tolist()
            columns.append({
                "column": str(name), "dtype": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "unique": int(series.nunique(dropna=True)), "examples": examples,
            })
        return _dump({"rows": int(len(frame)), "columns": int(len(frame.columns)), "fields": columns})

    def check_missing_values() -> str:
        counts = frame.isna().sum()
        result = [{"column": str(c), "missing_count": int(n),
                   "missing_ratio": float(n / len(frame)) if len(frame) else 0.0}
                  for c, n in counts.items()]
        return _dump({"rows": int(len(frame)), "by_column": result,
                      "most_missing": [str(c) for c in counts[counts == counts.max()].index]
                      if len(counts) and counts.max() > 0 else [],
                      "fully_empty_columns": [str(c) for c in frame.columns
                                              if len(frame) == 0 or frame[c].isna().all()]})

    def detect_outliers(column: str) -> str:
        if column not in frame.columns:
            return _dump({"error": f"Unknown column: {column}"})
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.empty:
            return _dump({"column": column, "error": "No numeric values to analyze."})
        q1, q3 = (float(values.quantile(0.25)), float(values.quantile(0.75)))
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (values < lower) | (values > upper)
        sample = [] if _is_sensitive(column) else values[mask].head(5).tolist()
        return _dump({"column": column, "method": "1.5xIQR", "q1": q1, "q3": q3,
                      "iqr": iqr, "lower_bound": lower, "upper_bound": upper,
                      "outlier_count": int(mask.sum()),
                      "outlier_ratio": float(mask.mean()), "sample_values": sample,
                      "interpretation": "Statistical outliers are candidates for review, not proof of errors."})

    def check_duplicates(subset: list[str] | None = None) -> str:
        if subset is not None:
            invalid = [c for c in subset if c not in frame.columns]
            if invalid:
                return _dump({"error": "Unknown column(s): " + ", ".join(invalid)})
            if not subset:
                return _dump({"error": "subset must contain at least one column, or be omitted."})
        duplicated = frame.duplicated(subset=subset, keep="first")
        return _dump({"scope": subset or "all columns", "duplicate_rows": int(duplicated.sum()),
                      "duplicate_ratio": float(duplicated.mean()) if len(frame) else 0.0,
                      "rows": int(len(frame))})

    def analyze_distribution(column: str, top_k: int = 10) -> str:
        if column not in frame.columns:
            return _dump({"error": f"Unknown column: {column}"})
        if not 1 <= top_k <= 50:
            return _dump({"error": "top_k must be between 1 and 50."})
        series = frame[column]
        numeric = pd.to_numeric(series, errors="coerce")
        if pd.api.types.is_numeric_dtype(series) or (series.notna().sum() and numeric.notna().sum() / series.notna().sum() >= 0.9):
            values = numeric.dropna()
            if values.empty:
                return _dump({"column": column, "error": "No numeric values to analyze."})
            return _dump({"column": column, "kind": "numeric", "count": int(values.count()),
                          "mean": float(values.mean()), "std": float(values.std()) if len(values) > 1 else 0.0,
                          "min": float(values.min()), "q25": float(values.quantile(.25)),
                          "median": float(values.median()), "q75": float(values.quantile(.75)),
                          "max": float(values.max())})
        counts = series.astype("string").value_counts(dropna=False).head(top_k)
        frequencies = [{"value": "[redacted]" if _is_sensitive(column) else str(k), "count": int(v)}
                       for k, v in counts.items()]
        return _dump({"column": column, "kind": "categorical", "unique_values": int(series.nunique(dropna=True)),
                      "top_frequencies": frequencies})

    def validate_data_types() -> str:
        """Flag text fields that look numeric or mix numeric and non-numeric values."""
        issues = []
        checked = 0
        for column in frame.columns:
            series = frame[column]
            if not (pd.api.types.is_object_dtype(series) or
                    pd.api.types.is_string_dtype(series) or
                    isinstance(series.dtype, pd.CategoricalDtype)):
                continue
            values = series.dropna()
            if values.empty:
                continue
            checked += 1
            parsed = pd.to_numeric(values.astype("string").str.strip(), errors="coerce")
            numeric_count = int(parsed.notna().sum())
            ratio = numeric_count / len(values)
            if ratio == 1.0:
                issue = "numeric_values_stored_as_text"
                invalid = values.iloc[0:0]
            elif ratio >= 0.2:
                issue = "mixed_numeric_and_non_numeric_values"
                invalid = values[parsed.isna()]
            else:
                continue
            examples = [] if _is_sensitive(column) else invalid.astype(str).head(5).tolist()
            issues.append({
                "column": str(column), "dtype": str(series.dtype), "issue": issue,
                "numeric_parseable": numeric_count, "non_null_values": int(len(values)),
                "invalid_count": int(len(invalid)), "sample_invalid_values": examples,
            })
        return _dump({
            "representation_hints": value_hints(frame),
            "text_columns_checked": checked, "issue_count": len(issues), "issues": issues,
            "note": "Heuristic check: numeric-looking text may be intentional; review before changing types.",
        })

    def check_correlations(columns: list[str] | None = None, threshold: float = 0.7) -> str:
        """Rank Pearson correlations between numeric columns; correlation does not imply causation."""
        if not 0 < threshold <= 1:
            return _dump({"error": "threshold must be greater than 0 and at most 1."})
        selected = columns if columns is not None else [
            str(column) for column in frame.select_dtypes(include="number").columns
        ]
        if columns is not None:
            invalid = [column for column in columns if column not in frame.columns]
            if invalid:
                return _dump({"error": "Unknown column(s): " + ", ".join(invalid)})
        selected = list(dict.fromkeys(selected))
        if len(selected) > 30:
            return _dump({"error": "Select at most 30 numeric columns at a time."})
        numeric = frame[selected].apply(pd.to_numeric, errors="coerce") if selected else pd.DataFrame()
        numeric = numeric.dropna(axis=1, how="all")
        if numeric.shape[1] < 2:
            return _dump({"columns": list(numeric.columns), "pairs": [],
                          "message": "At least two columns with numeric values are required."})
        matrix = numeric.corr(method="pearson")
        pairs = []
        names = list(matrix.columns)
        for left_index, left in enumerate(names):
            for right in names[left_index + 1:]:
                value = matrix.loc[left, right]
                if pd.notna(value):
                    pairs.append({"left": str(left), "right": str(right), "pearson_r": float(value)})
        pairs.sort(key=lambda pair: abs(pair["pearson_r"]), reverse=True)
        return _dump({
            "method": "Pearson correlation with pairwise complete observations",
            "threshold": threshold,
            "columns": names,
            "pairs": pairs[:20],
            "above_threshold": [pair for pair in pairs if abs(pair["pearson_r"]) >= threshold][:20],
            "note": "Correlation describes association, not causation.",
        })

    def compare_groups(group_column: str, metric_column: str, method: str = "auto") -> str:
        """Compare a numeric measure across categories, such as revenue by region."""
        if group_column not in frame.columns or metric_column not in frame.columns:
            invalid = [name for name in (group_column, metric_column) if name not in frame.columns]
            return _dump({"error": "Unknown column(s): " + ", ".join(invalid),
                          "available_columns": list(frame.columns[:30]),
                          "hint": "metric_column is a real data field. To count values, use method=count; keep the actual metric column name."})
        if method not in {"auto", "mean", "median", "sum", "count"}:
            return _dump({"error": "method must be auto, mean, median, sum, or count."})
        groups = frame[group_column]
        if method == "auto":
            numeric_values = pd.to_numeric(frame[metric_column], errors="coerce").notna().any()
            method = "count" if group_column == metric_column or not numeric_values else "mean"
        metric = frame[metric_column] if method == "count" else pd.to_numeric(frame[metric_column], errors="coerce")
        if method != "count" and metric.notna().sum() == 0:
            return _dump({"error": f"Column {metric_column!r} has no numeric values. To count text entries, keep this column and use method=count."})
        distinct = int(groups.nunique(dropna=False))
        if distinct > 30:
            return _dump({"error": "This comparison has more than 30 groups. Filter or combine categories first.",
                          "group_count": distinct, "limit": 30})
        work = pd.DataFrame({"group": groups, "metric": metric})
        grouped = work.groupby("group", dropna=False, observed=True)["metric"]
        results = []
        for key, values in grouped:
            non_null = values.dropna()
            if method == "count":
                value = int(len(non_null))
            elif method == "mean":
                value = float(non_null.mean()) if len(non_null) else None
            elif method == "median":
                value = float(non_null.median()) if len(non_null) else None
            else:
                value = float(non_null.sum()) if len(non_null) else None
            label = "[missing]" if pd.isna(key) else ("[redacted]" if _is_sensitive(group_column) else str(key))
            results.append({"group": label, "rows": int(len(values)), "metric_non_null": int(len(non_null)),
                            method: value})
        results.sort(key=lambda row: (row[method] is None, -(row[method] or 0)))
        return _dump({"group_column": str(group_column), "metric_column": str(metric_column),
                      "method": method, "groups": results,
                      "note": "Descriptive comparison only; group differences do not establish cause."})

    def inspect_date_column(column: str) -> str:
        """Parse a date-like field and report its usable range and invalid entries."""
        if column not in frame.columns:
            return _dump({"error": f"Unknown column: {column}"})
        original = frame[column]
        if pd.api.types.is_numeric_dtype(original):
            return _dump({"error": "Numeric date encodings need an explicit format or unit. Select a date-like text column."})
        parsed = pd.to_datetime(original, errors="coerce", utc=True, format="mixed")
        non_null_count = int(original.notna().sum())
        parsed_count = int(parsed.notna().sum())
        invalid_count = non_null_count - parsed_count
        sensitive = _is_sensitive(column)
        return _dump({
            "column": str(column), "non_null_values": non_null_count,
            "parsed_dates": parsed_count, "invalid_non_null_values": invalid_count,
            "parse_rate": float(parsed_count / non_null_count) if non_null_count else 0.0,
            "earliest": None if parsed_count == 0 else ("[redacted]" if sensitive else parsed.min().isoformat()),
            "latest": None if parsed_count == 0 else ("[redacted]" if sensitive else parsed.max().isoformat()),
            "note": "Parsing is heuristic. Date-like strings can be ambiguous; verify the source format.",
        })

    def generate_quality_report() -> str:
        """Create a shareable Markdown summary using aggregates only, with no row-level examples."""
        missing = frame.isna().sum().sort_values(ascending=False)
        missing_total = int(missing.sum())
        duplicate_count = int(frame.duplicated().sum())
        lines = [
            "# Data Quality Report", "", "## Dataset overview", "",
            f"- Rows: {len(frame):,}", f"- Columns: {len(frame.columns):,}",
            f"- Missing cells: {missing_total:,} / {frame.size:,}" if frame.size else "- Missing cells: 0",
            f"- Fully duplicated rows: {duplicate_count:,}", "",
            "## Fields", "", "| Field | Type | Missing | Missing rate | Unique |", "|---|---|---:|---:|---:|",
        ]
        report_columns = list(frame.columns[:30])
        for column in report_columns:
            series = frame[column]
            missing_count = int(series.isna().sum())
            rate = missing_count / len(frame) if len(frame) else 0.0
            column_label = str(column).replace("|", "\\|")
            lines.append(f"| {column_label} | {series.dtype} | {missing_count:,} | {rate:.1%} | {series.nunique(dropna=True):,} |")
        if len(frame.columns) > len(report_columns):
            lines.append(f"\nShowing {len(report_columns)} of {len(frame.columns)} fields.")
        lines.extend(["", "## Numeric summaries", "", "| Field | Count | Mean | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|"])
        numeric_columns = [column for column in frame.select_dtypes(include="number").columns if not _is_sensitive(column)]
        for column in numeric_columns[:8]:
            values = frame[column].dropna()
            if values.empty:
                continue
            column_label = str(column).replace("|", "\\|")
            lines.append(f"| {column_label} | {len(values):,} | {values.mean():.4g} | {values.median():.4g} | {values.min():.4g} | {values.max():.4g} |")
        if not numeric_columns:
            lines.append("| No non-sensitive numeric fields | — | — | — | — | — |")
        if len(numeric_columns) > 8:
            lines.append(f"\nShowing 8 of {len(numeric_columns)} non-sensitive numeric fields.")
        lines.extend(["", "## Review notes", ""])
        if len(frame) and missing_total:
            lines.append(f"- Missingness is {missing_total / frame.size:.1%} of all cells; check the fields with the highest missing counts.")
        if len(frame) and duplicate_count:
            lines.append(f"- {duplicate_count:,} rows are fully duplicated; confirm whether these are valid repeated records.")
        if not missing_total and not duplicate_count:
            lines.append("- No missing cells or fully duplicated rows were found by these checks.")
        lines.extend(["", "This report contains aggregate statistics only. Outliers and correlations require separate review; they do not establish data errors or causation."])
        return "\n".join(lines)

    def check_numeric_range(column: str, minimum: float | None = None, maximum: float | None = None) -> str:
        """Check user-specified inclusive bounds; this is not statistical outlier detection."""
        if column not in frame.columns:
            return _dump({"error": f"Unknown column: {column}"})
        if minimum is None and maximum is None:
            return _dump({"error": "Supply minimum, maximum, or both."})
        if any(bound is not None and not np.isfinite(bound) for bound in (minimum, maximum)):
            return _dump({"error": "Bounds must be finite numbers."})
        if minimum is not None and maximum is not None and minimum > maximum:
            return _dump({"error": "minimum must not exceed maximum."})
        original = frame[column]
        numeric = pd.to_numeric(original, errors="coerce")
        finite = numeric.notna() & np.isfinite(numeric)
        values = numeric[finite]
        below = values < minimum if minimum is not None else pd.Series(False, index=values.index)
        above = values > maximum if maximum is not None else pd.Series(False, index=values.index)
        return _dump({"column": column, "minimum": minimum, "maximum": maximum, "bounds": "inclusive",
                      "rows": len(frame), "checked_values": int(finite.sum()),
                      "missing_values": int(original.isna().sum()),
                      "invalid_numeric_values": int((original.notna() & ~finite).sum()),
                      "below_minimum": int(below.sum()), "above_maximum": int(above.sum()),
                      "violation_count": int((below | above).sum()),
                      "violation_ratio_of_checked": float((below | above).mean()) if len(values) else None,
                      "note": "Missing, non-numeric, and infinite values are counted separately from bound violations."})

    def compare_columns(left_column: str, right_column: str, mode: str = "auto", tolerance: float = 0.0) -> str:
        """Compare two fields row by row without exposing their raw contents."""
        invalid = [name for name in (left_column, right_column) if name not in frame.columns]
        if invalid:
            return _dump({"error": "Unknown column(s): " + ", ".join(invalid)})
        if mode not in {"auto", "exact", "numeric"}:
            return _dump({"error": "mode must be auto, exact, or numeric."})
        if mode == "auto":
            numeric_fields = all(pd.api.types.is_numeric_dtype(frame[name]) for name in (left_column, right_column))
            mode = "numeric" if tolerance != 0 or numeric_fields else "exact"
        if not np.isfinite(tolerance) or tolerance < 0 or (mode == "exact" and tolerance != 0):
            return _dump({"error": "Use a finite nonnegative tolerance in numeric mode only."})
        left, right = frame[left_column], frame[right_column]
        both_present = left.notna() & right.notna()
        one_missing = left.isna() ^ right.isna()
        if mode == "numeric":
            a, b = pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")
            comparable = both_present & a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
            matched = pd.Series(False, index=frame.index)
            matched.loc[comparable] = np.isclose(a[comparable], b[comparable], atol=tolerance, rtol=0)
        else:
            comparable = both_present
            matched = comparable & left.eq(right).fillna(False)
        mismatched = comparable & ~matched
        return _dump({"left_column": left_column, "right_column": right_column, "mode": mode,
                      "absolute_tolerance": tolerance, "rows": len(frame),
                      "compared_rows": int(comparable.sum()), "matched_rows": int(matched.sum()),
                      "mismatched_rows": int(mismatched.sum()), "one_side_missing_rows": int(one_missing.sum()),
                      "both_missing_rows": int((left.isna() & right.isna()).sum()),
                      "invalid_numeric_pair_rows": int((both_present & ~comparable).sum()),
                      "note": "Both-missing and invalid numeric pairs are not counted as matches. Exact mode is case-sensitive; numeric mode uses absolute tolerance only. No source values are returned."})

    def summarize_time_series(date_column: str, metric_column: str, frequency: str = "month", method: str = "sum") -> str:
        """Aggregate a field by observed UTC day, Monday-start week, or month."""
        invalid = [name for name in (date_column, metric_column) if name not in frame.columns]
        if invalid:
            return _dump({"error": "Unknown column(s): " + ", ".join(invalid)})
        if frequency not in {"day", "week", "month"} or method not in {"sum", "mean", "count"}:
            return _dump({"error": "frequency must be day/week/month; method must be sum/mean/count."})
        original_dates = frame[date_column]
        if pd.api.types.is_numeric_dtype(original_dates):
            return _dump({"error": "Numeric date encodings require explicit units. Use a date-like text column."})
        if _is_sensitive(date_column):
            return _dump({"error": "Time buckets for sensitive date fields are disabled by the column-name filter."})
        dates = pd.to_datetime(original_dates, errors="coerce", utc=True, format="mixed")
        if not dates.notna().any():
            return _dump({"error": "No valid dates to aggregate."})
        period = dates.dt.tz_localize(None).dt.to_period({"day": "D", "week": "W-SUN", "month": "M"}[frequency]).dt.start_time
        period_count = int(period.nunique())
        if period_count > 30:
            return _dump({"error": "More than 30 observed periods. Choose a coarser frequency.", "period_count": period_count})
        original_metric = frame[metric_column]
        metric = original_metric if method == "count" else pd.to_numeric(original_metric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        work = pd.DataFrame({"period": period, "metric": metric})
        periods = []
        for bucket, group in work.groupby("period", sort=True):
            values = group["metric"].dropna()
            if method == "count":
                value = len(values)
            elif not len(values):
                value = None
            else:
                value = float(values.sum()) if method == "sum" else float(values.mean())
            if value is not None and not np.isfinite(value):
                return _dump({"error": "Aggregation exceeded the finite numeric range."})
            periods.append({"period_start": bucket.strftime("%Y-%m-%d"), "rows": len(group),
                            "metric_non_null": len(values), "value": value})
        return _dump({"date_column": date_column, "metric_column": metric_column,
                      "frequency": frequency, "method": method, "timezone": "UTC", "periods": periods,
                      "missing_date_rows": int(original_dates.isna().sum()),
                      "invalid_date_rows": int((original_dates.notna() & dates.isna()).sum()),
                      "invalid_numeric_metric_rows": int((original_metric.notna() & metric.isna()).sum()) if method != "count" else 0,
                      "note": "Weeks begin Monday. Only observed periods are returned. Invalid dates are excluded; numeric methods exclude invalid or infinite metrics. A bucket with no valid numeric metrics has a null value. Duplicate rows are retained."})

    from .table_tools import build_table_tools
    from .rule_tools import build_rule_tools
    from .consistency_tools import build_consistency_tools
    from .chart_tools import build_chart_tools
    from .comparison_tools import build_comparison_tools

    return [
        StructuredTool.from_function(check_numeric_range, name="check_numeric_range",
            description="Check a numeric field against user-specified inclusive minimum and/or maximum. Use for business rules such as age 0..120 or nonnegative amount; not IQR outliers. Requires column and at least one bound."),
        StructuredTool.from_function(compare_columns, name="compare_columns",
            description="Reconcile two fields row by row. Requires left_column and right_column. Default mode=auto uses numeric comparison for a nonzero absolute tolerance or two numeric fields; otherwise exact. Explicit exact is case-sensitive; numeric supports tolerance (default 0). Missing/invalid pairs are separate. No raw values returned."),
        StructuredTool.from_function(summarize_time_series, name="summarize_time_series",
            description="Aggregate a metric over time using date_column and metric_column. frequency=day/week/month (default month); method=sum/mean/count (default sum). count supports text fields. UTC dates; weeks begin Monday. Maximum 30 observed periods."),
        StructuredTool.from_function(inspect_schema, name="inspect_schema",
            description="Inspect row/column counts, field types, completeness, unique counts, and a few sample values. Takes no arguments."),
        StructuredTool.from_function(check_missing_values, name="check_missing_values",
            description="Compute missing counts and ratios for every column. Takes no arguments."),
        StructuredTool.from_function(detect_outliers, name="detect_outliers",
            description="Find numeric outlier candidates with the 1.5xIQR rule. Requires an exact column name."),
        StructuredTool.from_function(check_duplicates, name="check_duplicates",
            description="Count redundant duplicate rows overall or within selected columns. This is NOT a per-category record count. Optional subset is a list of exact column names."),
        StructuredTool.from_function(analyze_distribution, name="analyze_distribution",
            description="Use for single-column category frequencies or value counts, such as counts of each status. Also computes numeric descriptive statistics for one field. Requires column; top_k defaults to 10."),
        StructuredTool.from_function(validate_data_types, name="validate_data_types",
            description="Check text columns for numeric-looking values or a mix of numeric and non-numeric values. Takes no arguments."),
        StructuredTool.from_function(check_correlations, name="check_correlations",
            description="Rank Pearson correlations among numeric columns. Optional columns selects exact field names; threshold defaults to 0.7. Correlation does not imply causation."),
        StructuredTool.from_function(compare_groups, name="compare_groups",
            description="Group by a category and aggregate a real metric_column. method=count counts non-null values, including text. mean/median/sum aggregate numeric measures. Default auto counts text or the grouping field itself, otherwise computes a numeric mean. Limit 30 groups. For single-field frequencies, prefer analyze_distribution."),
        StructuredTool.from_function(inspect_date_column, name="inspect_date_column",
            description="Check how well a date-like column parses and report its valid date range. Requires an exact column name."),
        StructuredTool.from_function(generate_quality_report, name="generate_quality_report",
            description="Build a concise Markdown data-quality report with schema, missingness, duplicate counts, and numeric summaries. Takes no arguments; excludes row-level samples."),
    ] + build_table_tools(frame) + build_rule_tools(frame) + build_consistency_tools(frame) + build_chart_tools(frame) + (
        build_comparison_tools(frame, reference_frame) if reference_frame is not None else [])


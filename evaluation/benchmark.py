"""Run a bounded 20-task model + tool benchmark and save results server-side."""

from __future__ import annotations

import json
import os
import sys
import time
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import run_agent


def make_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(579)
    frame = pd.DataFrame({
        "record_id": np.arange(100),
        "age": rng.integers(18, 80, size=100).astype(float),
        "spend": rng.normal(60, 15, size=100),
        "segment": rng.choice(["A", "B", "C"], size=100),
        "region": rng.choice(["North", "South", "West"], size=100),
    })
    frame.loc[[3, 14, 29], "age"] = np.nan
    frame.loc[[4, 19], "spend"] = np.nan
    frame.loc[77, "spend"] = 250.0
    frame.loc[88, "segment"] = None
    frame.loc[1] = frame.loc[0]
    return frame, pd.DataFrame(columns=frame.columns)


def parse_entry(entry: dict) -> dict | None:
    try:
        value = json.loads(entry["result"])
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def matches(check: str, logs: list[dict], frames: dict[str, pd.DataFrame]) -> bool:
    main, empty = frames["main"], frames["empty"]
    by_tool = {entry["tool"]: parse_entry(entry) for entry in logs}

    if check == "schema_shape":
        x = by_tool.get("inspect_schema")
        return bool(x and x.get("rows") == 100 and x.get("columns") == 5)
    if check == "schema_fields":
        x = by_tool.get("inspect_schema")
        return bool(x and {f["column"] for f in x.get("fields", [])} == set(main.columns))
    if check in {"missing_counts", "missing_age", "highest_missing", "missing_ratio", "multi_tool_missing_duplicates"}:
        x = by_tool.get("check_missing_values")
        if not x:
            return False
        observed = {row["column"]: row for row in x.get("by_column", [])}
        expected = main.isna().sum()
        if check in {"missing_counts", "multi_tool_missing_duplicates"}:
            if any(observed.get(col, {}).get("missing_count") != int(count) for col, count in expected.items()):
                return False
        if check == "missing_age" and observed.get("age", {}).get("missing_count") != int(expected["age"]):
            return False
        if check == "missing_ratio":
            row = observed.get("age", {})
            return abs(row.get("missing_ratio", -1) - float(expected["age"] / len(main))) < 1e-9
        if check == "highest_missing":
            return set(x.get("most_missing", [])) == set(expected[expected == expected.max()].index)
        if check == "multi_tool_missing_duplicates":
            dup = by_tool.get("check_duplicates")
            return bool(dup and dup.get("duplicate_rows") == int(main.duplicated().sum()))
        return True
    if check in {"spend_outliers", "age_outliers"}:
        col = "spend" if check == "spend_outliers" else "age"
        x = by_tool.get("detect_outliers")
        if not x:
            return False
        values = pd.to_numeric(main[col], errors="coerce").dropna()
        q1, q3 = values.quantile(.25), values.quantile(.75)
        mask = (values < q1 - 1.5 * (q3-q1)) | (values > q3 + 1.5 * (q3-q1))
        return x.get("outlier_count") == int(mask.sum()) and abs(x.get("q1", -1) - q1) < 1e-6
    if check in {"exact_duplicates", "segment_duplicates", "multi_tool_missing_duplicates"}:
        x = by_tool.get("check_duplicates")
        if not x:
            return False
        subset = ["segment"] if check == "segment_duplicates" else None
        if check == "multi_tool_missing_duplicates":
            subset = None
        return x.get("duplicate_rows") == int(main.duplicated(subset=subset).sum())
    if check == "age_distribution":
        x = by_tool.get("analyze_distribution")
        return bool(x and abs(x.get("mean", -1) - main["age"].mean()) < 1e-6
                    and abs(x.get("median", -1) - main["age"].median()) < 1e-6)
    if check == "segment_distribution":
        x = by_tool.get("analyze_distribution")
        return bool(x and x.get("unique_values") == int(main["segment"].nunique()))
    if check == "segment_top_counts":
        x = by_tool.get("analyze_distribution")
        if not x:
            return False
        observed = {row["value"]: row["count"] for row in x.get("top_frequencies", [])}
        expected = main["segment"].astype("string").value_counts().to_dict()
        return all(observed.get(str(value)) == int(count) for value, count in expected.items())
    if check == "empty_schema":
        x = by_tool.get("inspect_schema")
        return bool(x and x.get("rows") == 0 and x.get("columns") == len(empty.columns))
    if check == "empty_missing":
        x = by_tool.get("check_missing_values")
        return bool(x and set(x.get("fully_empty_columns", [])) == set(empty.columns))
    if check in {"invalid_distribution_column", "invalid_duplicate_subset", "invalid_top_k", "categorical_outlier"}:
        tool = {"invalid_distribution_column": "analyze_distribution", "invalid_duplicate_subset": "check_duplicates",
                "invalid_top_k": "analyze_distribution", "categorical_outlier": "detect_outliers"}[check]
        x = by_tool.get(tool)
        return bool(x and "error" in x)
    return False


def write_report(path: Path, report: dict) -> None:
    """Atomically persist progress so an interrupted run still has useful results."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded DataAudit model/tool evaluation.")
    parser.add_argument("--limit", type=int, help="Evaluate only the first N tasks (useful for a quick pilot).")
    parser.add_argument("--max-steps", type=int, default=3, help="Maximum tool rounds per task (default: 3).")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.max_steps < 1:
        parser.error("--max-steps must be at least 1")

    tasks = json.loads((PROJECT_ROOT / "evaluation" / "tasks.json").read_text(encoding='utf-8'))
    if args.limit is not None:
        tasks = tasks[:args.limit]
    main_frame, empty_frame = make_frames()
    frames = {"main": main_frame, "empty": empty_frame}
    results, tool_calls, valid_calls, numeric_scored, numeric_correct = [], 0, 0, 0, 0
    started_all = time.perf_counter()

    output = Path(os.getenv("DATAAUDIT_BENCHMARK_RESULTS", str(PROJECT_ROOT / "results" / "benchmark.json")))
    for index, task in enumerate(tasks, start=1):
        started = time.perf_counter()
        try:
            answer, logs = run_agent(task["question"], frames[task["dataset"]], max_steps=args.max_steps)
            called = {entry["tool"] for entry in logs}
            expected_present = set(task["expected_tools"]).issubset(called)
            valid = all(entry["status"] == "ok" and parse_entry(entry) is not None for entry in logs)
            accuracy = bool(matches(task["check"], logs, frames))
            elapsed = time.perf_counter() - started
            for entry in logs:
                tool_calls += 1
                valid_calls += int(entry["status"] == "ok" and parse_entry(entry) is not None)
            if task["numeric"]:
                numeric_scored += 1
                numeric_correct += int(accuracy and expected_present and valid)
            results.append({"id": task["id"], "success": expected_present and valid and accuracy,
                            "tool_calls_valid": valid, "numerically_correct": accuracy and expected_present and valid if task["numeric"] else None,
                            "expected_tools": task["expected_tools"],
                            "actual_tools": [entry["tool"] for entry in logs],
                            "seconds": elapsed, "answer": answer})
        except Exception as exc:
            results.append({"id": task["id"], "success": False, "tool_calls_valid": False,
                            "numerically_correct": False if task["numeric"] else None,
                            "expected_tools": task["expected_tools"], "actual_tools": [],
                            "seconds": time.perf_counter() - started,
                            "error": f"{type(exc).__name__}: {exc}"})
            if task["numeric"]:
                numeric_scored += 1
        print(f"[{index}/{len(tasks)}] {task['id']}: {results[-1]['seconds']:.2f}s; "
              f"success={results[-1]['success']}; tools={results[-1]['actual_tools']}", flush=True)

        # Checkpoint after each task; this is important for long-running local-model evaluations.
        checkpoint = {
            "model": os.getenv("MODEL_NAME", "qwen2.5-7b-instruct"), "seed": 579,
            "task_count": len(tasks), "completed_tasks": len(results), "complete": False,
            "task_success_rate": sum(r["success"] for r in results) / len(results),
            "tool_call_validity": valid_calls / tool_calls if tool_calls else 0.0,
            "tool_calls": tool_calls,
            "numerical_accuracy": numeric_correct / numeric_scored if numeric_scored else None,
            "numerical_tasks": numeric_scored,
            "average_execution_seconds": sum(r["seconds"] for r in results) / len(results),
            "total_execution_seconds": time.perf_counter() - started_all,
            "failure_cases": [r["id"] for r in results if not r["success"]], "tasks": results,
        }
        write_report(output, checkpoint)

    elapsed_all = time.perf_counter() - started_all
    report = {
        "model": os.getenv("MODEL_NAME", "qwen2.5-7b-instruct"), "seed": 579, "task_count": len(tasks),
        "completed_tasks": len(results), "complete": True,
        "task_success_rate": sum(r["success"] for r in results) / len(results),
        "tool_call_validity": valid_calls / tool_calls if tool_calls else 0.0,
        "tool_calls": tool_calls,
        "numerical_accuracy": numeric_correct / numeric_scored if numeric_scored else None,
        "numerical_tasks": numeric_scored, "average_execution_seconds": sum(r["seconds"] for r in results) / len(results),
        "total_execution_seconds": elapsed_all,
        "failure_cases": [r["id"] for r in results if not r["success"]], "tasks": results,
    }
    write_report(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, ensure_ascii=False, indent=2))
    print(f"Saved actual benchmark results to {output}")
    return 0 if not report["failure_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


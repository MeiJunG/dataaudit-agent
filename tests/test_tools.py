import json

import pandas as pd

from src.data_manager import load_csv
from src.tools import build_tools
from src.visualization import distribution_columns, distribution_figure, missingness_figure, overview_markdown


def test_quality_tools_return_computed_values():
    df = pd.DataFrame({"value": [1, 2, 3, 4, 100], "group": ["a", "a", "b", None, "b"]})
    tools = {tool.name: tool for tool in build_tools(df)}
    schema = json.loads(tools["inspect_schema"].invoke({}))
    assert schema["rows"] == 5 and schema["columns"] == 2
    missing = json.loads(tools["check_missing_values"].invoke({}))
    assert next(x for x in missing["by_column"] if x["column"] == "group")["missing_count"] == 1
    outliers = json.loads(tools["detect_outliers"].invoke({"column": "value"}))
    assert outliers["outlier_count"] == 1
    duplicates = json.loads(tools["check_duplicates"].invoke({}))
    assert duplicates["duplicate_rows"] == 0
    distribution = json.loads(tools["analyze_distribution"].invoke({"column": "value"}))
    assert distribution["mean"] == 22


def test_invalid_column_returns_error_without_reading_paths():
    tool = {tool.name: tool for tool in build_tools(pd.DataFrame({"x": [1]}))}["analyze_distribution"]
    result = json.loads(tool.invoke({"column": "/etc/passwd"}))
    assert "error" in result


def test_sensitive_column_values_are_not_exposed_in_tool_results():
    df = pd.DataFrame({"customer_id": ["C-1", "C-2", "C-3", "C-4", "C-5"],
                       "salary": [10, 20, 30, 40, 1000]})
    tools = {tool.name: tool for tool in build_tools(df)}
    schema = json.loads(tools["inspect_schema"].invoke({}))
    id_field = next(x for x in schema["fields"] if x["column"] == "customer_id")
    assert id_field["examples"] == []
    outliers = json.loads(tools["detect_outliers"].invoke({"column": "salary"}))
    assert outliers["outlier_count"] == 1 and outliers["sample_values"] == []


def test_sample_csv_loads_through_validated_data_manager():
    from pathlib import Path

    sample = Path(__file__).parents[1] / "examples" / "sample_data.csv"
    frame = load_csv(sample)
    assert frame.shape == (6, 4)
    assert frame["monthly_spend"].isna().sum() == 1


def test_visualizations_summarize_data_and_exclude_sensitive_fields():
    df = pd.DataFrame({"age": [20, 30, None, 40], "group": ["A", "B", "A", None],
                       "email": ["a@x", "b@x", "c@x", "d@x"]})
    assert "4 行" in overview_markdown(df)
    assert distribution_columns(df) == ["age", "group"]
    missing = missingness_figure(df)
    assert list(missing.data[0].x) == [1, 1]
    hidden = distribution_figure(df, "email")
    assert len(hidden.data) == 0
    assert "敏感字段" in hidden.layout.annotations[0].text



def test_date_like_categories_keep_invalid_labels_and_default_to_numeric_fields():
    df = pd.DataFrame({'order_date': ['2026-10-01', 'not-a-date'], 'amount': [10, 20]})
    assert distribution_columns(df) == ['amount', 'order_date']
    fig = distribution_figure(df, 'order_date')
    assert fig.layout.yaxis.type == 'category'
    assert set(fig.data[0].y) == {'2026-10-01', 'not-a-date'}

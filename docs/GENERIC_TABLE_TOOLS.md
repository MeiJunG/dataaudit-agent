# Generic table and workbook tools

Uploads have no business-domain whitelist, required worksheet names or required field names. The home page starts without a dataset. Fictional domain examples are optional and collapsed. Files still need rectangular tables with a usable header row; titles, merged headings and multiple disjoint tables may require selecting a different sheet/header or reorganizing the file.

## Five new tools

| Tool | Contract |
| --- | --- |
| `list_workbook_sheets` | Actual workbook names, paginated 20 at a time, at most 50 sheets per accepted workbook. CSV/TSV have no sheets. |
| `inspect_sheet_layout` | Top 1–12 rows, first 20 columns; nonempty/text cell counts and up to three heuristic header candidates. It does not select a header automatically. |
| `query_rows` | Select up to 10 fields; up to four literal conditions joined by AND or OR; stable sorting; preview up to 20 logical data rows. |
| `aggregate_rows` | Filter first, then count rows or sum/mean/median/min/max a field. Up to three grouping fields and 30 observed groups. Missing grouping keys are retained. |
| `calculate_row_metric` | Per-row sum, mean, product, ordered difference/ratio, explicitly weighted sum/mean. Optional grouped aggregation, sorting and bounded preview. Source data remains unchanged. |

All five tools bind to the session's current upload. The model cannot supply arbitrary filesystem paths. `sheet` must be an actual name; `header_row` is a 1-based physical row. Reading another sheet does **not** change the chart/preview source selected in the UI. Each calculated result and exported trace records the actual sheet, header row and original-file SHA-256. Private upload paths are not exported.

A valid workbook with a blank first sheet can still be opened for worksheet discovery. Select a usable sheet in **读取设置**, or ask the Agent to inspect it. The layout tool supplies candidates rather than certifying a table boundary; all-text data rows can resemble headers. No workbook names or business types are hardcoded in the tool selection.

## Calculation semantics

- `count` counts matched rows, including rows with missing metrics; numeric aggregations separately report valid, missing and invalid values. An empty numeric aggregate is null, not zero.
- Conditions support `eq/ne/gt/ge/lt/le/contains/is_null/not_null`; `contains` is literal, not regular expression. Numeric comparisons exclude invalid/nonfinite values. Null operators reject a value argument. CSV/TSV reject invented worksheet names. Null checks are explicit. With no filters, all rows are included.
- Row metrics use complete numeric input rows. Exclusions are counted in priority order: missing input, invalid/nonfinite input, zero denominator, nonfinite calculation. No automatic imputation, currency/unit conversion or financial interpretation.
- Difference and ratio use exactly two ordered fields. An entirely nonnumeric calculation field is an error, rather than a successful all-invalid metric. Weighted operations require explicit weights (one per field); weighted means divide by the sum of weights, which must be nonzero.
- Previews use logical 1-based data-row positions, not physical CSV lines or worksheet row numbers. Sensitive-looking fields are hidden by a column-name heuristic; this is not a complete privacy classifier.
- Previews, groups and model observations are bounded. Full computed results remain in UI/export; the model receives compact samples and must not infer omitted values.

## Agent integration

A hierarchical model selector first chooses chart, generic tables, or ordinary quality analysis. Ordinary checks then receive a second focused family selection; generic tables receive a focused `tables` tool family for workbook discovery, multi-condition queries, multiple grouping fields and row arithmetic. Routing accepts either a valid selector function call or an exact allowlisted text category; it never interprets free-form prose as a data-tool call. Real analysis tools still require structured calls. The actual LangGraph loop remains `model → tool → observation → model`, with at most six rounds and a duplicate-call guard. Current-table tasks with an attached reference also receive tool-family selection after data-scope selection. `general` exposes a bounded mixed subset to reduce context pressure; lower-level `run_agent(..., tool_family=None)` retains all base tools for direct callers.

The UI renders numeric tables directly from successful computed observations. This does not bypass the Agent's observation-to-decision loop. Errors and limits remain visible. The default V100 model and optional candidate process remain unchanged.

## Inspiration and scope

Reviewed primary repositories and documentation on 2026-11-07:

- [PandasAI](https://github.com/Sinaptik-AI/pandas-ai): natural-language queries, visualization and multiple DataFrames inspired generic table discovery/querying.
- [Microsoft Data Formulator](https://github.com/microsoft/data-formulator): inspect data sources and preserve exploration context before interpreting results.
- [DuckDB SELECT](https://duckdb.org/docs/2.0/sql/query_syntax/select): selected fields and computed expressions informed bounded relational operations. DuckDB itself is a database, not an Agent.

This implementation uses existing Pandas/LangGraph dependencies; it does not install these projects, copy their code, run arbitrary model-generated Python/SQL, or claim their full connector, join or chart capabilities. Joining arbitrary worksheets is not yet implemented.

## Reproduction

```sh
python -m pytest tests checks -q
python -m evaluation.check_generic_web --output results/generic-web.json
```

`examples/generic_workbook.xlsx` is a tiny synthetic workbook with a blank cover, arbitrary sheet names, non-first-row headers, Unicode field names, missing inputs and invalid text. The eight live prompts are development fixtures, not a held-out benchmark or proof that every spreadsheet layout is supported. See the compact evidence record in `evaluation/generic-tables.summary.json` and browser checks in `docs/GENERIC_VISUAL_QA.json`.


## Recorded outcome

198 automated tests passed. The final eight real-model workbook tasks passed 8/8 (24.16 seconds total in this single development run); the original 11 domain/chart requests and five reference/current-only requests also passed. Prior complete generic runs scored 5/8, 6/8, 7/8 and 2/8, illustrating routing fragility rather than steady improvement. Failures remain in the compact evidence record.

The browser showed a genuine recovery: the model added `Sheet1` to a CSV row-product call, received the explicit no-worksheets error, removed the parameter and computed correct grouped totals. This is one observed recovery, not a claim that every malformed task self-corrects. Chrome file upload requires the extension's file-URL permission; this session verified arbitrary-workbook uploads through the API, not browser uploading.

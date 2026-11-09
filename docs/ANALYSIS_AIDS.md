# Analysis aids: question suggestions, column overview, number check, CSV export

Inspired by the interaction patterns of PandasAI, Data Formulator and ChatGPT's data analysis (suggested prompts, downloadable results, a visible data profile). No code was copied. None of these features calls the model or fixes a tool sequence; the Agent loop is unchanged.

| Feature | Module | Behaviour |
|---|---|---|
| **试试这样问** | `src/suggestions.py` | Up to 5 starter questions built from detected column *types* (number / category / date-like). No business templates; sensitive-looking column names are skipped. Choosing one only fills the question box. |
| **数据概览** | `src/suggestions.py` | Per column: inferred type, missing count, distinct values, range or most frequent values. Sensitive columns show no values. Types are inferred for display only and are never saved as rules. |
| **数字核对** | `src/grounding.py` | When the answer shown is the model's own free text, numbers in it are compared with numbers in the executed tools' arguments and results (rounding and percent forms allowed; single-digit integers are ignored as too ambiguous). Unmatched numbers are listed under 计算过程. Most answers are rendered directly from tool results and are not affected. This is a consistency check, not proof that a claim is right. |
| **下载结果表** | `src/result_tables.py` | The latest filter / aggregate / row-calculation table as UTF-8 CSV (BOM for Excel), max 5000 rows. Text cells starting with `= + - @` are prefixed with `'` to avoid spreadsheet formula injection. |

Tests: `tests/test_new_features.py`.

## Reproduction script (Python)

After a row query, aggregation or per-row metric, "下载复现脚本 · Python" exports a standalone pandas script
(`src/repro_script.py`). It re-reads the original file, applies the same conditions and numeric handling,
and prints the results so they can be checked outside the app.

- Only `query_rows`, `aggregate_rows` and `calculate_row_metric` are exported; other steps are listed in a comment.
- All values from the analysis are written with `repr()`, never pasted as code.
- A group with no valid values yields missing (as in the tool), not 0.
- Not mirrored: hidden-column masking, 120-character cell caps, and the application's import heuristics.
- `tests/test_repro_script.py` runs the generated script and compares its numbers with the tool results.

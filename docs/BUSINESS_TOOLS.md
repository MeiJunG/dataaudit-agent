# Business data checks

The Agent can select these tools from a natural-language request. All three operate on the active uploaded CSV, return computed observations, and leave its contents unchanged. See `examples/reconciliation.csv` for a synthetic demonstration.

## Explicit numeric limits

Ask: “检查 amount 是否在 0 到 250 之间。”

`check_numeric_range(column, minimum=None, maximum=None)` checks inclusive limits. At least one finite bound is required. A minimum larger than the maximum is an error. Missing, non-numeric, and infinite values are counted separately and excluded from the checked-value denominator. Values exactly at a boundary pass.

This tests a business rule supplied by the user. Use `detect_outliers` for the statistical IQR rule. The Agent is instructed not to invent business limits.

## Row-by-row reconciliation

Ask: “逐行核对 amount 和 recorded_amount，允许 0.01 的绝对误差，缺失单独统计。”

`compare_columns(left_column, right_column, mode="auto", tolerance=0)` compares fields within each row. Auto mode uses numeric comparison if tolerance is nonzero or both fields have numeric types; otherwise it uses exact, case-sensitive value equality. Explicit `mode="numeric"` also supports numeric strings. Numeric comparison uses absolute tolerance and zero relative tolerance.

The response distinguishes:

- Comparable pairs that match or differ.
- Rows missing one side.
- Rows missing both sides.
- Both-present pairs that cannot be interpreted as finite numbers in numeric mode.

Both-missing pairs are not counted as matches. No source values are returned. Explicit exact mode rejects a nonzero tolerance rather than silently ignoring it.

## Time totals, averages, and counts

Ask: “按 order_date 的自然月汇总 amount 总额。”

`summarize_time_series(date_column, metric_column, frequency="month", method="sum")` supports day, week, and month buckets; methods are sum, mean, and count. Count includes non-null text or numeric values. Sum and mean require finite numeric values. Numeric date encodings are rejected because their units would otherwise be ambiguous.

Dates are parsed and normalized to UTC. Weeks start Monday. Invalid or missing dates are excluded, with separate counts. Only observed buckets are returned, and duplicate rows are retained. A period with no valid numeric values returns null for sum/mean rather than a misleading zero. More than 30 observed periods requires a coarser frequency. Sensitive-looking date fields are blocked by the existing column-name filter.

Invalid metric counts are reported across the input; invalid metrics and invalid dates can overlap in the same row. Do not add those counts as though they were disjoint.

## Evidence and failures

The first live English reconciliation case omitted numeric mode while specifying a tolerance. The original tool rejected that combination; the model then invented counts. Auto mode now handles this natural request, and regression tests cover the omitted-mode case.

The Agent also replaces a model's final answer when there are no successful tool observations, or when the latest tool round entirely failed. It reports the failure instead of accepting unsupported data conclusions. This guard is not a general verifier of every sentence: a model can still misdescribe a successful tool result, and the development scorer does not automatically grade its prose.


## Formatting focused answers

Live web checks found that a model could contradict correct counts or add an unperformed outlier check when summarizing tool output. For a focused request that successfully uses only these three tools (and optionally schema inspection), the final answer is now formatted directly from complete structured observations. It includes both missing-pair categories and distinguishes missing dates from missing metrics. The model still chooses its actions and can continue through the Agent loop; the renderer does not prescribe a tool sequence.

Mixed requests involving other analysis tools continue to use the model's final prose. Their generated statements are not covered by this formatter's guarantees.

To exercise actual upload, tool selection, and final displayed wording through the web API:

```bash
python evaluation/check_business_web.py --output results/business-web.json
```

This is an opt-in integration check requiring the running app and model. It is excluded from the default CPU-only pytest suite.

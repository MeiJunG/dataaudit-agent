# Rule checks and conditional statistics

The three tools work on the active table without changing it. The language model selects the tools and arguments. Focused answers are rendered from successful computed observations rather than model-authored counts.

## Allowed categories

Ask: “status 只允许 completed、pending、cancelled，区分大小写。检查列表外的值。”

`validate_categories(column, allowed_values, case_sensitive=True)` requires an explicit list of 1–50 permitted strings. Missing values are separate, not counted as unexpected categories. Whitespace is not trimmed. Case sensitivity can be disabled explicitly. Up to ten unexpected categories are shown; examples for sensitive-looking fields are hidden.

## Primary-key candidates

Ask: “检查 order_id 能否作为主键，缺失和重复分别统计。”

`check_key_uniqueness(columns)` accepts 1–10 exact field names, including composite keys. It reports rows missing any key component and excludes those rows from the duplicate-key check. `duplicate_key_rows` counts every participant in a repeated key; `redundant_rows` counts only rows beyond the first. A usable candidate requires a nonempty table, no missing components, and no duplicate complete keys. No key values are returned.

## Filter then aggregate

Ask: “只看 status 等于 completed 的订单，amount 总额是多少？”

`filter_and_aggregate(filter_column, operator, value, metric_column=None, method="count")` applies one condition. Operators are `eq`, `ne`, `gt`, `ge`, `lt`, `le`, and literal `contains`. There is no expression evaluation, SQL, or regular-expression execution. Text comparisons are case-sensitive.

Count without a metric returns matched rows; count with a metric returns its non-null count. Sum, mean, min, and max require a metric and exclude missing, non-numeric, and infinite values. An empty numeric aggregate is null, not zero. Missing filter values never match, even for `ne`. Numeric comparisons exclude invalid or infinite filter values. Returned counts distinguish matched rows from usable metric values; raw matched records are not returned.

## Synthetic example

The “规则示例” action loads `examples/rule_checks.csv`, containing eight synthetic records.

| Check | Reference result |
|---|---|
| Status in completed/pending/cancelled, case-sensitive | 2 unexpected values: unknown and Completed |
| Same list, ignoring case | 1 unexpected value: unknown |
| order_id as key | 1 row missing a key; 2 repeated-key participants; 1 redundant row |
| Composite order_id + region | No duplicate complete keys, but 1 missing key remains |
| Exact status = completed, sum amount | 4 matched rows; 3 usable amounts; sum 330; 1 missing amount |

These are development fixtures, not independent evaluation data. The primary-key and category checks validate only the supplied rules; they do not establish every business constraint.

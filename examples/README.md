# Synthetic office orders

`office_orders.csv` is hand-authored demo data. It contains no real customer or employee records.

Try these questions in the web UI after uploading the file:

- “amount 缺失了多少？有多少完全重复行？”
- “按 region 比较 amount 的平均值。”
- “检查 order_date 有没有无法识别的日期。”
- “生成一份完整的质量检查报告。”

Reference answers for inspection:

| Check | Expected result |
|---|---:|
| Rows / columns | 9 / 6 |
| Missing amount | 1 |
| Fully duplicated rows, keeping the first | 1 |
| Invalid non-null dates | 1 |
| East mean amount | 120 |
| West mean amount | 53.333333… |
| North mean amount | 270 |

These statistics include the duplicated row and exclude missing amounts from means. The agent does not alter or deduplicate the uploaded data. This is a demonstration fixture, not independent evaluation evidence.


## Reconciliation data

`reconciliation.csv` is a synthetic eight-row fixture for the three business checks. Upload it and try:

- “检查 amount 是否在 0 到 250 之间。”
- “逐行核对 amount 和 recorded_amount，允许 0.01 的绝对误差，缺失单独统计。”
- “按 order_date 的自然月汇总 amount，总额是多少？”

Reference calculations:

| Check | Expected result |
|---|---|
| Inclusive amount range 0..250 | 7 finite values checked; 1 below, 2 above; 1 missing |
| Numeric reconciliation, absolute tolerance 0.01 | 6 comparable pairs; 5 match, 1 differs; 1 one-sided missing, 1 both missing |
| October amount total, valid dates only | 670 |
| Invalid dates | 1 |
| Week starting September 28 | 250 |
| Week starting October 5 | 420 |

The invalid-date row contains amount 400 and is excluded from time totals. It is included in the numeric-range and field-comparison checks because those checks do not depend on dates. These tools do not edit the CSV. Weeks begin Monday and timestamps are normalized to UTC. Only observed periods are returned; empty calendar periods are not filled in. Numeric reconciliation uses absolute tolerance with relative tolerance fixed to zero.

## Rule-check data

`rule_checks.csv` contains eight synthetic rows for the “规则示例” action. Try:

- “status 只允许 completed、pending、cancelled，区分大小写。检查列表外的值。”
- “检查 order_id 能否作为主键，同时检查缺失和重复键。”
- “只看 status 等于 completed 的记录，计算 amount 总额，缺失单独统计。”

Expected results: two values outside the case-sensitive allowed list; one row missing order_id; two rows participating in the repeated order_id, of which one is redundant; four completed rows, three non-null amounts, total 330. Primary-key checks and filtered statistics are independent: a missing key does not automatically remove that row from a filtered total. See [full semantics](../docs/RULE_TOOLS.md).

`office_reference.csv` is a six-row synthetic reference for `office_orders.csv`. It has constant amount=100, a different month, balanced regions, a legacy_note column and no quantity column. It is used for deterministic schema, missing-rate, mean and category-share comparison checks.


## Multi-sheet Excel import fixture

[multi_sheet_orders.xlsx](multi_sheet_orders.xlsx) contains fictional instruction, October and September sheets. Select 十月订单 with header row 3, then optionally use 九月订单 with header row 1 as a reference. Duplicate and blank headers are intentional import cases. The October amount mean is 15 and September mean is 8. See [table imports](../docs/TABLE_IMPORTS.md) for the supported format and value semantics.


## Cross-domain workbook

[domain_examples.xlsx](domain_examples.xlsx) contains fictional 成绩、销售、股价、库存、问卷 and 格式与单位 worksheets. The five normal domains are available from 更多示例…; the formatting sheet can be selected from the worksheet controls. Prices are artificial calendar-day values, not market observations. The [support matrix](../docs/DOMAIN_SUPPORT.md) gives exact fixture values and operation limits.


## Generic workbook

`generic_workbook.xlsx` contains only synthetic data. It starts with an empty cover sheet (`empty-7B`), followed by arbitrary names (`Measure_41`, `Lookup-Z`). The data header in `Measure_41` is on row 3. Names are fixture data, not application presets.

Upload it, then ask “这个文件里有哪些工作表？” or “先检查 Measure_41 的表头在哪一行，再计算 Metric B 的合计。” The expected sum is 21. Select `Measure_41` / row 3 in reading settings for preview/charting. A per-row `Metric A × Metric B` grouped sum is L=100 and R=320; missing and invalid inputs remain excluded, without changing the file.

The website starts empty. All earlier business examples are opt-in under **示例文件 · 可选**.

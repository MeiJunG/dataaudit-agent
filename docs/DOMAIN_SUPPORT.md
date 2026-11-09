# Content domains and supported operations

The importer accepts **four file formats**: `.xlsx`, `.xls`, `.csv` and `.tsv`. Grades, sales and stock prices are content domains, not additional file formats. DataAudit operates on the selected table's real columns; it does not require a fixed business schema or classify a file into a predefined domain before allowing analysis.

The current implementation has 20 current-table tools plus an optional reference-comparison adapter. These support descriptive analysis and explicit checks. Reading an Excel workbook does not mean every domain-specific operation, spreadsheet layout or business rule is supported.

## Try five content domains

Use **更多示例…** in the file bar. Selecting an example loads the data, resets prior analysis/reference/history and fills a starter question, without calling the model. All examples are fictional. The workbook [domain_examples.xlsx](../examples/domain_examples.xlsx) also lets you select the six individual worksheets through the normal import controls.

| Content | Examples of available tasks | Rules/limits the user must supply or respect |
|---|---|---|
| Grades | Subject means/distributions, class comparisons, missing scores, counts above a supplied threshold | Passing mark, absence policy, weighting and denominator for rates are not inferred. Row-wise total/weighted-grade calculation and named-student rankings are not implemented |
| Sales | Sum by region, monthly totals, literal status filters, refunds, missing amounts | Negative refunds are retained. Currency/unit conversion and row-wise price×quantity are not implemented; supply a prepared amount field |
| Stock prices | Uploaded historical price/volume summaries and bounded date-line charts | One selected numeric series, no automatic multi-ticker separation, market-data download, candlesticks, corporate-action adjustment, return/technical-indicator calculation or forecasts |
| Inventory | Counts below a supplied threshold, category counts, missing/duplicate item keys | No inferred reorder policy, replenishment optimization or automatic row-wise comparison of different safety-stock fields |
| Surveys | Rating means, category frequencies, grouped summaries, missing responses | No inferred reverse scoring, questionnaire scale, weighting or population-level statistical claims |

The examples test operations already exposed by the tools, rather than adding five hardcoded agents. Arbitrary uploaded column names are still supported. Semantic ambiguity, such as whether a grade rate excludes absent students or whether sales are net of refunds, needs a clear question.

## Reference fixture values

- **成绩**: six rows, subject `数学` has one missing score. Its five scores average **74**; four records meet a user-specified `>=60` condition. Class means are `200/3` and `85`. Student identifiers are text with leading zeros.
- **销售**: five rows, one missing amount, one negative refund. Completed rows sum to **3500**; all finite amounts sum to **3300**. Monthly totals are **3500** and **-200**. Excel displays the stored `.13` tax rate as 13%.
- **股价**: a single artificial `DEMO` series on **45 consecutive calendar days**, including weekends; it is not real trading data. First/last close are **100** and **122**. One middle price is missing and remains a gap. No price is forward-filled.
- **库存**: five rows, three quantities below a user-specified 10. One item key repeats: two participating rows, one redundant occurrence.
- **问卷**: six responses; five non-missing rating values average **3.4**. Four satisfaction categories plus a missing response are retained. Boolean recommendation fields are read as booleans.
- **格式与单位**: intentionally unnormalized currency, percent, unit-bearing numbers and non-ISO dates. These support warning tests, not numeric result claims.

## Representation hints

Imports now record aggregate `value_hints` for common numeric-text/date patterns: percent signs, currency symbols/thousands separators, unit suffixes, and non-ISO date strings. The reading settings show these warnings; `validate_data_types` also returns them. The model receives up to four compact hints as untrusted metadata. Actual values are never converted by these warnings.

For example, `￥1,200`, `$800`, `85%`, `30万元`, `10kg` and `01/02/2026` cannot be assumed to share one numeric unit or date interpretation. The user should prepare uniform values and meaningful headers. Matching is heuristic; it is not a universal locale, unit or date parser. A legitimate categorical value may match a pattern. Counts describe pattern matches, not automatically erroneous cells.

Excel formatting and stored values remain different: a numeric 20% cell commonly stores `0.2`. Source dates/units still need interpretation, and the uploaded bytes stay unchanged. For detailed worksheet, formula-cache, header and file restrictions see [TABLE_IMPORTS.md](TABLE_IMPORTS.md).

## Longer time-series charts

The original shared chart limit was 30 points. Category bars remain limited to **30 groups**, while date lines now support **366 observed periods**. Longer series must use a coarser frequency or a prepared subset. No silent sampling or truncation occurs. The separate tabular `summarize_time_series` tool retains its **30-period** output limit.

A date line aggregates the selected table by UTC day/week/month. It does not automatically split by ticker or another category; users should upload/select a single series or preprocess that grouping. All-invalid metric groups remain null. Entirely absent dates are not inserted: adjacent observed dates may be joined by a line, which does not create measurements for missing dates.

For more than 30 chart points, the next model observation contains point count, null count, parameters/exclusions and first/last two points. Full ordered data stays in the trace, UI and JSON/HTML exports. The Agent still receives a tool observation and decides whether to continue; the graph is not bypassed. The model is explicitly told not to infer intermediate values from endpoint samples.

## Validation scope

`tests/test_domain_diversity.py` checks actual imported values, rule parameters, chart boundaries at 366/367, preserved missing prices, warnings without mutation, example resets and the compact-observation/full-trace contract. `evaluation/check_domain_web.py` exercises eleven synthetic requests against the running model. These are development prompts and fixtures, not certification for all gradebooks, financial datasets, stock feeds or survey designs.


## Tool-family routing and column spelling

The first flat-tool live run passed 7/11 cases. Failures included a threshold count answered through category grouping, a literal inventory threshold mistaken for a second column, a price line drawn as daily row counts, and mixed full/half-width parentheses in a sales field name. These failures are retained; they are not counted as successful analyses.

The application and CLI now use `run_routed_agent`: an initial model call chooses profile, filter, chart, rules, groups, dates, report or general tools. The bounded observation-to-model loop then uses that subset. The later generic-tool update gives general a bounded mixed subset for context limits; see GENERIC_TABLE_TOOLS.md. This selection is made by the model, not keyword rules or domain labels. Reference-attached tasks retain the existing reference/current-table scope selector. `run_agent` remains the lower-level bounded loop used by simulated-model tests and accepts an optional tool family.

Column arguments preserve exact names when possible. If an unknown field spelling has exactly one match after Unicode NFKC normalization and outer-space trimming, that name is resolved to the actual column. Ambiguous matches fail rather than choosing one. Filter values, allowed categories, units and numbers are not normalized. Trace/export records preserve requested arguments, executed arguments and the resolution; repeated-call checks recognize both spellings.


## Recorded outcome

The final run passed **11/11 of the same development prompts**, following earlier **7/11** and **8/11** runs. The first family router still confused key checks and category frequencies, and the chart agent still selected row counts for the requested numeric line. The final router uses explicit bilingual task priorities and family-specific instructions, preserving model-based selection. All three runs and failed arguments/answers are retained in [the compact record](../evaluation/domain-diversity.summary.json).

The final server suite passed **180 tests (144 dependency-based, 36 standard-library) in 12.35 seconds**. Existing follow-up/session and reference/current-only regressions each passed **5/5**. Browser checks covered the five-option menu, preset questions, a grade mean, an actual 45-point price chart with a null middle value, completed JSON downloading with source hash/routing/arguments, representation warnings and worksheet resets. Desktop/mobile geometry passed at 1280/390px. See [browser QA](DOMAIN_VISUAL_QA.json).

These outcomes are checks of synthetic fixtures and prompts used during development. They do not establish support for every specialized analysis or every spreadsheet arrangement.

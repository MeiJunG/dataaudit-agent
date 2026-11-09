# Ask for a chart

The twentieth Agent tool, `create_chart`, turns a natural-language request into a computed chart specification. The Agent chooses parameters; Pandas/NumPy compute the values; Plotly displays and exports them. No model-generated program is executed. The original CSV is unchanged.

## Try it

Load **订单示例**, type a request, and select **开始分析**:

- `按 region 分组，用 amount 合计画柱状图。`
- `画 region 的订单记录数柱状图，按行计数。`
- `画 amount 的直方图。`
- `按 order_date 每天汇总 amount 合计，画折线图。`

The left panel opens **生成的图表** after the chart callback receives a successful tool observation. Hover to inspect values. **下载图表 · HTML** exports a self-contained interactive file; its JavaScript is included, so it opens without a CDN connection. Exports stay on the server until downloaded. The **画图** shortcut suggests a real, non-sensitive-looking column from the active dataset; it does not start inference automatically.

Replacing or removing data clears the prior answer, trace and download, and the chart callback restores the normal distribution panel. Each analysis displays the latest successful chart in that request; it is not a multi-chart dashboard or conversational chart editor.

## Tool contract

`create_chart(chart_type, x, y=None, method="count", frequency="month")`

| Parameter | Meaning |
|---|---|
| `chart_type` | `bar`, `histogram`, or `line` |
| `x` | Exact column name; categories, a numeric distribution, or ISO dates respectively |
| `y` | Required for sum/mean; omitted for row counts and histograms |
| `method` | `count` counts all group rows, including those without a metric; `sum`/`mean` use finite numeric values |
| `frequency` | Date lines only: day, Monday-starting week, or month; UTC |

Bar results contain at most 30 groups; date-line results contain at most 366 observed periods. Excess groups return an explicit error; no silent top-k truncation. Category labels over 256 characters are rejected. Histograms compute ten equal-width bins; the final bin includes its right endpoint. Duplicate records remain counted. Missing categories and missing/invalid dates are excluded. Numeric aggregates exclude missing, invalid or infinite metrics and preserve all-invalid groups as null rather than zero.

`plotted_rows` counts rows with a valid x, before metric exclusions; `excluded_x_rows` and `excluded_metric_rows` explain the separate exclusions. Only observed time periods are returned. A line connects observed points, which does not imply measurements between them or fill absent dates with zero.

Fields whose names trigger the existing sensitive-field heuristic are refused for charts. That heuristic does not identify every sensitive field or value. Category labels and numeric aggregates can still reveal information; use only authorized datasets.

## Implementation and provenance

- `src/chart_tools.py`: validated tool arguments and computed observations.
- `src/agent_charts.py`: bounded specification validation, escaped labels, deterministic completion text and HTML export.
- `app.py`: chart tab, download and reset callbacks.
- `tests/test_agent_charts.py`: aggregation, UTC boundaries, missing/invalid values, limits, sensitivity, offline export, resets and a simulated observation-to-model loop.
- `evaluation/chart_tasks.json`: eight bilingual drawing requests with fixed reference values; `twenty_tasks.json` includes these plus the prior 42 tasks.
- `evaluation/check_chart_web.py`: live chart and download callbacks, not a browser rendering test.

The interaction was inspired by [Microsoft Data Formulator](https://github.com/microsoft/data-formulator), which combines natural language and visual exploration, and [PandasAI](https://github.com/sinaptik-ai/pandas-ai), which supports conversational analysis and visualization. We reviewed their public READMEs. This implementation was written within DataAudit's existing tool loop; neither project was cloned, installed, or copied into this repository. Their broader features are not claimed here.


## Recorded server validation

On the V100, using the existing Qwen2.5-7B-Instruct Q4_K_M service at context 4096, maximum output 256 and temperature 0:

- 25 standard-library checks passed; 86 dependency-based tests passed in 8.16 seconds.
- First 50-task model run: **48/50 in 76.075 seconds**. A numeric-summary request chose unrelated tools and exhausted the three-round budget; a Chinese daily chart had correct values but a truncated final explanation.
- Added explicit single-column summary guidance and allowed a matching time-aggregate observation to accompany deterministic chart completion text. Regression tests verify that mismatched frequencies and unrelated analysis are not silently hidden by chart formatting.
- Second full run: **50/50 in 76.611 seconds**, including all eight bilingual chart requests. This scores computed evidence and bounded completion, not every possible sentence or arbitrary dataset.

Both runs use `evaluation/twenty_tasks.json`, SHA-256 `ae753ca304e2be1ac77b1ebea77bc5b4fb4299a08db721c8f0f0e1c3c48d8619`, with three tool rounds. Full raw traces are retained on the server as `twenty-baseline.json` and `twenty-baseline-final.json`; compact public evidence is recorded separately. These are synthetic prompts used during development and debugging, not held-out tests or general reliability estimates. Browser rendering and real HTML downloading were subsequently verified; see [visual QA](VISUAL_QA.json).

Live Gradio verification passed all three chart types, inspected the served self-contained HTML files, and confirmed dataset-switch and clear/reset outputs. The client API omits tab-layout updates; unit checks cover returned selection values. [Compact evidence](../evaluation/twenty-chart.summary.json) preserves both model runs and these web results. Resetting the UI removes the link, but exported files remain in the server output directory until explicitly cleaned up.


Lines longer than 30 periods return a compact model observation while keeping every computed point in the actual trace and exports. The separate tabular time-summary tool retains a 30-period limit. See [cross-domain behavior](DOMAIN_SUPPORT.md).

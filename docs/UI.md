# Interface notes

The current interface is a compact CSV workbench: a file toolbar, a single summary strip, a chart panel, and a question/result panel. It uses a neutral blue-gray palette with one indigo accent. It does not use a large slogan or a file sidebar.

## Layout and interaction

- The file toolbar contains upload, the active filename, four synthetic examples, and a clear action.
- The office example is shown initially and explicitly labeled “示例”. Its metrics are calculated from the actual fixture; displaying it does not call the language model.
- Four measurements share one strip: rows, columns, missing cells, and redundant fully duplicated rows.
- The chart panel switches between missingness and numeric/category distribution. Counts use integer ticks for small fixtures; histograms use separated bins.
- Questions and results sit beside the chart. Focused business/rule answers use calculated observations; the calculation record is collapsed.
- The report action is a download button rather than a visible server filename.
- The tool library uses grouped rows with a name, short description, and explicitly labeled example question.
- Narrow screens stack the panels and wrap file actions; the earlier 16-tool layout at a 390-pixel viewport was inspected for horizontal overflow and then reset.

## Copy and consistency

Use concrete actions such as “查空值”, “查重复”, “类别检查”, “主键检查”, and “条件统计”. Avoid marketing copy, “质量信号”, invented benefits, or runtime details in everyday navigation. Keep implementation details in the collapsed section and project documentation.

Preserve the same output/reset contract for uploads, examples, and clearing data. A new dataset invalidates previous answers, traces, and report links. Do not imply that a displayed example belongs to the user or automatically launch model inference on page load.

## Verification

The 19-tool iteration passed 25 standard-library cases plus 68 dependency-based tests. The current chart iteration passes 25 plus 86; see [chart validation](CHARTS.md). Coverage includes example loading, clearing results, escaped filenames, chart defaults, safe literal filters, category-case rules, missing and composite keys, and rendering key findings alongside missing/duplicate helpers.

The earlier 36-task development evaluation exercised 16 tools and passed on the recorded run. The current 19-tool baseline passed 42/42; see [validation](VALIDATION.md). Separate live web checks covered all three new rule tools plus complete report download; the three earlier business web checks also passed. This verifies those fixtures and paths, not arbitrary data or every generated statement. That earlier check used synthetic rule data; the current screenshot shows a computed order total by region.

The Sites skill's design and local-preview workflow was applied within the existing Gradio deployment. Styling and presentation helpers are centralized in `src/interface.py`; `build_demo()` keeps page construction out of module import side effects.


## Current refinements

The deployed app adds a five-row, eight-column expandable data preview, masking sensitive-looking fields and escaping text. Execution records show readable names, duration and completion/error badges; parameters and raw results remain collapsed. A fourth synthetic example covers text formatting, conditional required fields and date ordering. Typography and spacing were adjusted without changing the basic workbench structure.

These callbacks were exercised against the running Gradio application: live model requests passed all three consistency checks, previewed data redacted order IDs, clearing reset the preview and previous results, and uploading a CSV then downloading its complete report succeeded. This verifies endpoint/state behavior but does not prove browser rendering or all client-side interactions. That callback-only stage did not include a new screenshot. Actual browser verification and current captures are recorded below.


## Natural-language charts

The latest update adds a third chart tab, **生成的图表**, a context-aware **画图** shortcut, and **下载图表 · HTML**. **开始检查** is now **开始分析** to cover both checks and charts. The tool catalog contains 20 entries. A successful chart callback selects the generated-chart tab; clearing the trace restores the distribution panel. The generated chart is derived from the tool observation, including explicit exclusions and aggregation semantics. See [CHARTS.md](CHARTS.md). Browser rendering has now been checked; see the current visual verification below.


## Session-history refinements

The centered container is now capped at 1260px, with 22px desktop card padding, stronger secondary-text contrast, slightly larger question/result text, and a compact code-native chart mark. The question panel has a **新问题** action and a plain follow-up hint. **本次分析记录** sits below the preview and restores prior results. Calculation rows are collapsed under a summary that distinguishes tool execution time from full model latency. Callback configuration tests cover shared state and atomic dataset resets; current browser verification is recorded below.


## Actual browser verification — 2026-11-07

Browser control was available on a fresh inventory check. The first navigation returned `net::ERR_CONNECTION_REFUSED` because the old local SSH forwarding process was absent. After restoring forwarding, a fresh tab opened the running app. No server/model restart was needed to restore that connection.

Observed at 390×844, 768×1024 and 1280×720 CSS pixels: the document width matched the viewport width, the cards stacked on narrow screens, and the desktop container was centered (measured center offset 0). The mobile tool library displayed 20 wrapped entries without page overflow. Temporary viewport overrides were reset afterwards.

The first visual inspection found **新问题** compressed to 22px wide and 61.5px high, causing vertical text. Its CSS now prevents flex shrinking and enforces 68px width plus nowrap. The corrected control measured 68×32px at all three tested widths. Only the app was restarted for that style change; inference processes stayed running.

Actual browser interactions covered CSV file selection/upload (the page showed the uploaded six-row fixture), chart generation, changing totals to means, history restoration, the fresh-question action while keeping history, dataset-switch resets, redacted preview cells, and a completed HTML download. The downloaded 4,860,035-byte file contained inline Plotly JavaScript and no external script source. The browser console error list was empty at completion. The file chooser tool call itself was unusually long; this was not treated as an application latency measurement.

Current captures: [desktop](images/workbench.jpg), [mobile](images/workbench-mobile.jpg). Machine-readable details: [VISUAL_QA.json](VISUAL_QA.json). These are viewport/browser spot checks, not exhaustive device or accessibility testing. Earlier paragraphs describing unavailable browser access are historical records of those earlier iterations.


## Reference comparison refinement

The current catalog has 20 base tools and one optional reference adapter. The reference selector sits in a compact accordion below the chart; generated comparisons show paired missing rates or focused category shares. The result tables use thin borders and a subdued header, and explanatory notes are separate paragraphs. Below 1100px the two main cards stack, avoiding cramped result columns at medium widths. On phones, wide tables scroll locally, and footer labels use separate lines.

The JSON record link is updated after analysis/restore/reset completion and uses an explicit attachment endpoint. Browser verification included the completed download and original-question/two-file-fingerprint checks. [REFERENCE_VISUAL_QA.json](REFERENCE_VISUAL_QA.json) records the current checks. The 20-tool screenshots and earlier browser outcomes discussed above are historical; current desktop/mobile captures show a real two-table category comparison.


## Excel import controls

The upload buttons now accept Excel/CSV/TSV. Explicit import settings expose worksheet and header-row choices; both sides of a reference comparison have independent selections. Header mappings and saved-formula guidance appear beside these controls. A real workbook with Chinese headers, a title row, duplicate and blank names was uploaded and analyzed through the browser. The settings fit within both tested viewport widths; preview table borders use the same subdued tone as result tables. [Excel visual QA](EXCEL_VISUAL_QA.json) and [current capture](images/excel-import.jpg) record the observed outcomes.


## Content-domain examples

更多示例… loads fictional grades, sales, a single price series, inventory or surveys. It resets prior context and fills a starter question without starting inference. Reading settings show representation warnings for common currency/percent/unit/date text without changing values. A real browser verified the menu, 45-point price chart and null gap, completed record download, and 390/1280px geometry. Current captures: [workspace](images/domain-workbench.jpg), [mobile](images/domain-mobile.jpg); [QA record](DOMAIN_VISUAL_QA.json).


## Generic table iteration

The page now starts empty and all fictional domain examples live under a closed **示例文件 · 可选** section. Worksheet names and field names come from the actual upload. The 26-item catalog includes five new workbook/query/calculation capabilities. Computed row/group tables identify the sheet/header actually read; reading another worksheet does not replace the preview source.

Actual desktop/mobile captures show a row-product grouped calculation and JSON download; the tool log preserves an invented-CSV-sheet error followed by the model's corrected call. 1280/390px geometry passed. Browser uploading remains unverified in this iteration because Chrome extension file-URL access is disabled; live API import checks cover the arbitrary-name workbook separately. See [GENERIC_VISUAL_QA.json](GENERIC_VISUAL_QA.json), [desktop](images/generic-workbench.jpg), [empty start](images/generic-empty.jpg), and [mobile](images/generic-mobile.jpg).

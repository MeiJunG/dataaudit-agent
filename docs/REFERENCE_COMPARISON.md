# Reference CSV comparisons and analysis records

This iteration adds a reference-aware `compare_datasets` tool to the existing 20 tools, plus downloadable JSON analysis records. The comparison tool is offered to the model only when a valid reference is attached. The other tools continue to use the current table.

## Try it

1. Load **订单示例** as the current table.
2. Expand **对照另一份表 · 可选**. Upload a reference CSV or choose **参考示例**.
3. Click **对照**, then **开始分析**, or ask `和参考表比，amount 的缺失率和均值变了吗？`.
4. The answer shows computed schema changes and selected-field statistics. The chart panel displays paired missing rates. Ask `这次只对照 region 的类别比例。` to narrow the comparison.
5. Use **下载分析记录 · JSON** to save the exact question, answer, parameters and computed observations. Restoring a historical result changes the active export to that result.

Changing the current dataset clears the reference and history together. Changing/removing the reference clears the old answer, report and history while keeping the current table. Starting a new question retains the archive but clears the displayed result and export. A failed/empty visible trace cannot keep a stale JSON download link.

## Computation contract

`compare_datasets(columns=None)` compares schema, row counts and redundant duplicate-row counts globally, then up to six shared columns. An explicit selection must contain 1–6 distinct exact names present in both tables. Schema added/removed name lists show at most ten names, with total counts recorded separately. Unexamined shared-field counts are explicit.

- Missing rates use actual null counts, separately in each table. Empty-table rates and gaps are undefined, displayed as a dash.
- Numeric fields require both inferred dtypes to be numeric (booleans are categorical). Means use finite non-null values. Mean change is current minus reference; standardized change divides by the reference population standard deviation (`ddof=0`) and is undefined for empty/constant references.
- Categorical TVD is half the L1 distance between non-null exact category frequencies. It ranges from zero (same proportions) to one (disjoint support). It is omitted/undefined for empty distributions or over 1000 categories. For up to three categories with the largest share differences, short and unambiguous aggregate labels/counts/rates are returned. A single categorical-field comparison displays these shares directly; longer/ambiguous labels omit this detail.
- A numeric/text type mismatch is reported without guessing a conversion. Sensitive-looking field names omit distribution statistics but retain completeness metadata. This name heuristic is not a complete privacy classifier.
- Duplicate rows stay in the distributions. These are descriptive differences between the supplied samples, not a statistical drift test, a model-performance evaluation or an automatic error verdict.

The chart uses tool observations: missing rates for a multi-field comparison, or category shares for a focused categorical comparison. Null rates remain undefined for zero-row datasets. It is not inferred from prose. Its offline HTML can be downloaded just like a generated single-table chart.

## Agent context and evidence

An initial flat-tool model probe computed the comparison but failed on the following model request: the full observation produced a 4220-token prompt, exceeding the existing 4096 context. The full result remains in the trace, UI and exported record. The next model decision now receives a compact JSON observation containing row counts, schema changes, selected-field missing counts, means and TVD. In reference mode, prior task context is limited to 384 UTF-8 bytes. The model still receives the observation and makes the next decision; it is not bypassed by a fixed comparison pipeline.

## JSON record contract

The record contains a schema version, run/parent IDs, the exact recorded question and answer, actual tool arguments/status/duration/observations, and model/dataset metadata. CSV SHA-256 values identify the original selected file bytes; they do not hash a normalized or modified DataFrame. Column names and dimensions are recorded, with a separate fingerprint for the reference.

The exporter does not read environment credentials and whitelists metadata fields. It includes tool observations and may contain dataset-derived values, field names and user questions; it is not a privacy-anonymization format. Source CSV rows are not embedded as a separate dataset. JSON artifacts are content-addressed, limited to 1 MiB and stored on the server. UI resets remove links rather than deleting previous exports. A programmatically constructed frame without source-file metadata has a null fingerprint.

## Sources and scope

- [Evidently](https://github.com/evidentlyai/evidently): current/reference data reports and structured report exports.
- [whylogs](https://github.com/whylabs/whylogs): compact dataset profiles and tracking dataset characteristics.
- [Ragas](https://github.com/vibrantlabsai/ragas): reviewed as an evaluation-oriented project; no Ragas scoring or LLM judge is claimed in this feature.

These repositories informed feature selection. No repository code or dependencies were copied or installed; the calculations, tool adapter, state handling, chart and exporter were implemented within DataAudit.


### Scope routing

Two flat-tool trials each passed 3/4 reference prompts and selected a current-only distribution tool for an elliptical reference follow-up. The implementation now follows the [LangGraph routing pattern](https://docs.langchain.com/oss/python/langgraph/workflows-agents#routing): when a reference exists, an initial model call selects `reference_comparison` or `current_table`, using the current request and bounded prior task choices. The selected agent loop receives only relevant tools and instructions: the comparison adapter, or the original 20 current-table tools. The router requests at most 96 output tokens; the data-agent loop retains its existing output/round limits.

Scope selection is performed by the model, not keyword rules. Invalid structured scope output raises an error rather than silently choosing a different table. The chosen scope and routing duration are recorded in the first tool-log entry and preserved in the JSON export. With no reference, the original agent path skips routing. Both scopes still run the observation-to-model tool loop. This is one local model with routed tool sets, not a claim of multiple independent agents or Ragas-based evaluation.


## Recorded outcomes

The final scope-routed run passed all four original bilingual reference-comparison cases, including the elliptical region follow-up, plus a fifth current-only chart request while the reference remained attached. Real reference upload, paired chart generation, exact-question JSON export, both CSV hashes, reference clear, history/export reset and current-dataset reset also passed. The earlier context-overflow probe and both 3/4 flat-tool runs are retained server-side. The final server unit run passed 148 tests (112 dependency-based cases and 36 standard-library checks) in 9.57 seconds. These are synthetic development prompts used during debugging, not held-out reliability estimates.


## Browser and downloads

Actual browser checks and current screenshots are in [REFERENCE_VISUAL_QA.json](REFERENCE_VISUAL_QA.json). JSON downloading initially failed despite a successful API file check. Gradio served the record inline; changing the UI to a same-origin link alone did not fix it in the in-app browser. The app now mounts Gradio under a small FastAPI app with an explicit attachment response for `/analysis-records/analysis-<64 lowercase hex characters>.json`. Other names, missing files and symlinks return 404; response headers disable caching and MIME sniffing. No arbitrary file path is accepted. This route uses the same localhost-only service and is not a public sharing or authentication mechanism.

The final browser download completed and its JSON matched the recorded question and both source-file hashes, even after the visible question had been edited without submission. The export link refreshes after analysis, history restore and reset actions. Raw model traces and generated artifacts stay on the server; the repository keeps compact validation summaries and screenshots.

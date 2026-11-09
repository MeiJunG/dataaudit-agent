# Validation record

## Generic workbook tools

The final server suite passed **198 tests (162 dependency-based and 36 standard-library) in 15.30 seconds**. Eight generic-workbook development requests passed **8/8 in 24.16 seconds**, including blank-cover discovery, header inspection followed by a sum, AND/OR filtering, multiple group fields, grouped products, weighted means and division exclusions. Existing domain/chart requests passed **11/11** and reference/current-only checks passed **5/5** on this version. These are synthetic development prompts used during debugging, not held-out reliability.

Earlier complete generic runs scored **5/8, 6/8, 7/8 and 2/8**. The final two-layer model router resolved severe tool-family overlap; required aggregation methods, finite-column validation, preview bounds and explicit header/condition semantics addressed parameter errors. An earlier run ended after two observed cases because the API harness did not refresh worksheet dropdown choices. All recorded failures and actual computed results remain in [generic-tables.summary.json](../evaluation/generic-tables.summary.json). The existing sales-filter scorer was broadened only to accept the new mathematically equivalent aggregation tool, with its field, literal condition, population and sum all checked.

Actual Chrome checks verified the empty initial workspace, optional example section, 26-item catalog, row-product/grouped totals, completed JSON download with source hash and routing, and a real failed-parameter → corrected-call sequence. Desktop 1280px and mobile 390px had no horizontal page overflow. Browser file upload was **not** verified: the Chrome extension lacks file-URL access and rejected `fileChooser.setFiles`; arbitrary workbook import/analysis was exercised through the live Gradio API. See [browser evidence](GENERIC_VISUAL_QA.json). Both preexisting model processes remain running; only the project web app was restarted.

## Cross-domain iteration

The final server suite passed **180 tests (144 dependency-based and 36 standard-library) in 12.35 seconds**. The same eleven cross-domain prompts improved from 7/11 to 8/11 to 11/11 after family routing, explicit intent priorities, numeric-chart instructions and unambiguous field-spelling resolution. The earlier wrong counts/tool selections remain recorded. Existing session and reference regressions each passed 5/5. See [domain evidence](../evaluation/domain-diversity.summary.json), [operation matrix](DOMAIN_SUPPORT.md) and [actual browser QA](DOMAIN_VISUAL_QA.json). These are synthetic development cases, not a held-out benchmark.

## Excel and varied input iteration

Server checks passed **166 tests (130 dependency-based and 36 standard-library cases) in 10.30 seconds**. Live model requests passed **6/6** synthetic cases across Chinese XLSX means/charts, different-sheet comparisons, TSV, GB18030 CSV and legacy XLS. The existing CSV comparison/current-only regression passed **5/5** after the reader and model wording changes. Exact selected sheets, header rows, mappings and original file hashes were verified in exported JSON. See [compact evidence](../evaluation/table-imports.summary.json), [import semantics](TABLE_IMPORTS.md) and [actual Excel browser checks](EXCEL_VISUAL_QA.json).

The browser exercised XLSX upload, current/reference worksheet choices, third-row headers, visible column mappings, Chinese preview redaction, computed chart/comparison results, completed JSON downloading and worksheet-change resets. Desktop/mobile geometry checks passed at 1280/390px. API-harness corrections for omitted layout outputs and explicit dropdown-choice refresh are recorded separately from the model results. These are development fixtures and prompts, not held-out reliability estimates.

## Reference comparison iteration

The reference-aware model routing and comparison/export changes passed 148 tests (112 dependency-based cases and 36 standard-library checks) in 9.57 seconds. Two flat-tool reference trials passed 3/4 cases each; routed tool sets passed the same four cases plus an attached-reference/current-only regression. Exact question and data fingerprints, uploads, chart callbacks and reference/history/export resets were checked. Full development evidence and failures are documented in [REFERENCE_COMPARISON.md](REFERENCE_COMPARISON.md).

Development check on 2026-11-07 using Python 3.12.10, Tesla V100-PCIE-16GB, Qwen2.5-7B-Instruct Q4_K_M, and the direct dependencies in `requirements-tested.txt`.

## Actual browser verification

Browser control was available and used. Restored an absent localhost SSH forward, verified responsive layouts at 390/768/1280px, fixed a 22px-wide button, and exercised upload, charts, follow-ups, history, resets, preview redaction and HTML downloading through the UI. Current reference-comparison screenshots and measurements are in [REFERENCE_VISUAL_QA.json](REFERENCE_VISUAL_QA.json); the earlier session checks remain in [VISUAL_QA.json](VISUAL_QA.json). Earlier unavailable-browser notes below are historical.

## Earlier session-history iteration

Server checks passed **32 standard-library cases and 97 dependency-based tests**. The first live follow-up run passed 5/5 groups: Chinese/English chart-average and daily-to-monthly changes plus restore-and-continue from an earlier result. New-question archive retention, dataset and clear resets, and separate-session empty history also passed. All three chart/download cases, three consistency-tool checks and exact report restoration after a different task passed on this app. These exercise callbacks and fixed fixtures, not browser rendering or general conversational reliability. See [session behavior](SESSION_HISTORY.md).

## Previous chart iteration (20 tools)

The natural-language chart update passed **25 standard-library checks and 86 dependency-based tests**. The first model run passed 48/50; after fixing single-column summary guidance and chart completion formatting, the second run passed **50/50 in 76.611 seconds**. Both raw runs are preserved. All three live chart/download cases and dataset/clear reset checks passed. See [chart behavior and validation](CHARTS.md) for configuration, failures and scope. These results are synthetic development evidence, not independent benchmarks.

## Previous deployed 19-tool iteration

The source transfer succeeded after renewed authorization. Server verification passed **25 standard-library checks and 68 dependency-based tests**. The 42-task development suite passed **42/42 in 62.353 s** on the existing Qwen2.5-7B server. These cases include six bilingual consistency requests and are not an independent general benchmark.

A live Gradio client loaded the consistency example, made all three new requests, verified computed answer text and readable trace summaries, checked preview redaction, and cleared the state. A CSV upload followed by report generation produced a complete 880-character Markdown artifact equal to the tool's report; switching datasets cleared the old answer/trace/download outputs.

The current model process stayed PID 11495. New app source was restarted separately. Browser review was unavailable at that historical stage; the current browser check is recorded at the top of this document. API checks remain separately scoped.

Qwen3-4B-Instruct-2507 Q4_K_M was downloaded directly to the server through an available mirror after the upstream server connection failed. Its bytes were checked against SHA-256 obtained from the original repository metadata; see the model comparison record for the live trial outcome and limits.

## Qwen3 candidate outcome

Qwen3-4B-Instruct-2507 Q4_K_M was actually loaded on the V100 and passed a plain English API request. The equal-budget (4096 context / 256 output) trial passed 40/42 in 56.078 s. The two report failures first exposed truncated tool-call arguments; raising output alone exposed 4096-context overflow. At 8192 context / 512 output, both focused report probes and the full 42/42 suite passed, with a 60.540 s full run. Those expanded-budget results are not ranked as equal-budget improvement.

The current app continues using Qwen2.5. The baseline model was never stopped; only the owned candidate process was restarted for its context change. Candidate GPU memory was observed at 3900 MiB (4K) and 4908 MiB (8K), alongside the baseline's 5506 MiB. See [full comparison details](MODEL_COMPARISON.md).

## Regression checks (earlier deployed version)

Latest server run: **63 passed in 6.10 seconds**, and the test process exited normally with code 0. The earlier 19-test result predates the expanded evaluation and upload-state checks.

The CPU suite covers numeric tools, invalid fields, sensitive examples, mixed text types, correlated and constant columns, mixed date strings, text counts, group means, report completeness beyond preview limits, report storage, tool-error classification, and the observation-to-model loop with a simulated model. It also checks truncated model answers, the maximum tool-round budget, and CLI overwrite protection.

GitHub Actions is configured for Python 3.11 and 3.12. The workflow has not been run on GitHub yet; local server results do not establish that both CI jobs pass.

## Sixteen-tool workbench iteration

The latest full development evaluation passed 36/36 computed-evidence cases in 50.051 seconds on the V100. All 16 tools appeared. Two prior 35/36 results are retained in the [evaluation record](../evaluation/sixteen-tool-v1.summary.json), including the distinction between category row frequencies and non-null metric counts.

The three new rule tools and report download passed four live web checks. A primary-key request may call missing-value or duplicate helpers as well; their successful results are now rendered alongside the key findings with distinct labels. The downloaded report was compared with its complete tool artifact. The earlier three business web checks were also rerun against the workbench.

The current UI has a compact file bar, a single summary strip, tabbed charts, and a separate question/result pane. It starts with explicitly labeled synthetic sample data; no model request runs automatically. The new layout was inspected at the default 989-pixel preview width and a 390-pixel narrow viewport, then the override was reset. The screenshot shows an actual filtered total from the running app.

## Earlier interface refresh

The app now combines upload, charts, questions, and results in one workspace. The synthetic office and reconciliation examples can be loaded without choosing a local file. The old API callback names and upload-state reset contract remain available.

Browser checks covered the default 989-pixel desktop preview and a 390-pixel narrow viewport; the narrow page had no horizontal overflow. The viewport override was reset afterwards. Example loading, quick questions, a live Chinese missing-value answer, and a report with a 940-byte download link were inspected through the actual UI. All three existing business web-integration checks passed using the new UploadButton component.

The screenshot in `docs/images/workbench.jpg` was captured from the running application using synthetic data. Numeric columns are prioritized in the chart selector, and date-looking category labels keep an explicit categorical axis so invalid labels are not silently dropped. UI checks do not replace the separate live-model evaluation of tool evidence.

## Thirteen-tool business-check iteration

The latest suite passed 30/30 computed-evidence checks in a single 39.548-second V100 run. It includes the earlier 24 cases plus six bilingual requests using the synthetic reconciliation fixture. All 13 tools appeared. One intermediate invalid-column error occurred in the category-frequency case; the model corrected its arguments on the next round and produced the correct result. The initial 29/30 result and its unsupported final-answer failure are recorded in the [evaluation history](../evaluation/README.md).

New regression coverage includes inclusive limits, non-finite input classification, numeric tolerance inference, separate missing-pair counts, UTC normalization, weekly boundaries, null numeric buckets, and the 30-period cap. The Agent suppresses unsupported model conclusions when no tool succeeded or the last tool round entirely failed. Focused business answers are now rendered from complete observations because initial web checks exposed incorrect paraphrases despite correct tool calculations. All three live web checks subsequently passed assertions on displayed counts, missing-pair categories, and time totals. Mixed analyses and other tool responses still use model prose; this is not a general prose-factuality guarantee.

## Earlier expanded evaluation and upload replacement

The ten-tool development suite passed 24/24 cases in 27.747 seconds; two additional paraphrase regression cases passed in 2.427 seconds. All ten tools appeared in the execution traces. See [the evaluation method](../evaluation/README.md) for the initial failure, the scorer correction, and the limitations of a development set.

The UI clears old answers, execution logs, and report links when a CSV is replaced, removed, or fails to load. Upload and analysis share a concurrency group. A live `gradio_client` session generated a report for the 9-row office fixture, uploaded the 6-row sample fixture, verified cleared answer/trace/download outputs, and obtained the new 6-row, 4-column schema from the model. Page construction is deferred to `build_demo()`; importing callback functions for CPU tests no longer constructs a Gradio app or leaves page-created background threads preventing process exit.

## Earlier live model requests

Synthetic `examples/office_orders.csv` was used. Measured times are individual development observations, not benchmark averages.

| Request | Observed tool | Result | Time |
|---|---|---|---:|
| Generate a quality report | `generate_quality_report` | Correct 9 rows, 6 columns, 1 missing cell, 1 duplicate | 3.431 s |
| Compare mean amount by region | `compare_groups` | North 270, East 120, West 53.333333… | 1.401 s |
| Web upload → agent request → report download | `generate_quality_report` | Complete 940-character Markdown verified, including final paragraph | 2.312 s |

The first report request exposed a truncated final model answer under the 256-token output setting. The system prompt now asks for a brief summary, a length-limit fallback is explicit, and the complete report is independent of answer length. The web request passed after that correction.

The web flow was exercised through `gradio_client` against the running app, including an actual synthetic CSV upload and file download. Uploaded data was retained in that client session for the subsequent agent request.

The model service remained the same running process throughout deployment. GPU memory observed after checks was 5510 MiB of 16384 MiB. This is a point-in-time measurement, not peak memory or a stress test.

## Evidence limits

- Historical 20/20 task results in the README belong to the earlier five-tool baseline.
- The ten-tool cases were used during debugging. They are not an independent benchmark or a long-duration reliability study; generated prose accuracy is not automatically scored.
- New live requests used synthetic office data and a five-value synthetic outlier fixture. No real user datasets were used.
- The llama.cpp source checkout lacks Git metadata, so its exact commit remains unrecorded. Pinning the server source and model checksum is still needed for fully reproducible published performance results.
- No public repository, public deployment, or GitHub CI run is claimed by this record.

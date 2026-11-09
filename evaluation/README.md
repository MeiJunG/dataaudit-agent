# Live tool evaluation

The default unit tests simulate model responses and do not establish live tool-selection reliability. This directory also contains sequential development evaluations that call the configured model API.

## Current 19-tool suite and Qwen3 trial

`nineteen_tasks.json` extends the suite to 42 cases covering all 19 tools. The default Qwen2.5 model passed 42/42 in 62.353 seconds. Qwen3-4B passed 40/42 with the same 4096-context/256-output budget and 42/42 with an 8192-context/512-output configuration. Context/output differences and the failed report probes are preserved in the [trial record](nineteen-model-trial.summary.json) and [model comparison notes](../docs/MODEL_COMPARISON.md).

```bash
python evaluation/expanded.py --tasks evaluation/nineteen_tasks.json --output results/nineteen.json
python evaluation/check_consistency_web.py --output results/consistency-web.json
```

The web check calls the live Gradio API for three consistency tasks, readable execution summaries, redacted data preview, and reset behavior. Upload and full-report download were additionally verified against the running app. Browser rendering was not inspected because local browser use was disabled in Work settings. Tests and API checks must not be represented as screenshot QA.

## Earlier 16-tool suite

```bash
python evaluation/expanded.py --tasks evaluation/sixteen_tasks.json --output results/sixteen.json
python evaluation/check_rules_web.py --output results/rules-web.json
```

The 36 cases retain the earlier 30 questions and add six bilingual requests for category rules, key candidates, and filtered totals. The new fixture has eight synthetic rows. Final tool-evidence result: **36/36 in 50.051 s**, with all 16 tools represented. The [compact record](sixteen-tool-v1.summary.json) includes actual per-task times and four passing web checks (three rule tools plus report download).

Both initial runs scored 35/36. In the first, a single-column frequency request turned into a grouped numeric mean after argument errors. In the second, a non-null amount count was mistaken for the number of status records. Group aggregation now infers a count for text or the grouping field itself when no method is specified, supplies actionable field errors, and is explicitly distinguished from single-column frequency analysis in the model instructions. The original question was retained; no incorrect count was reclassified as passing.

One intermediate error observation remains in the final run and is preserved in the full server trace. Success means the required computed evidence was ultimately returned within the bounded loop, not that no intermediate mistake occurred. These are debugging/development cases and are not an independent benchmark. The compact summary does not replace full traces or measure long-run reliability.

## Earlier 13-tool suite

```bash
python evaluation/expanded.py --tasks evaluation/thirteen_tasks.json --output results/thirteen.json
```

This retains the original 24 questions and adds six bilingual cases for explicit numeric bounds, reconciliation with an absolute tolerance, and monthly totals. The additional fixture is `examples/reconciliation.csv`.

Initial result: **29/30** in 38.596 seconds. The English reconciliation request omitted `mode=numeric` while including tolerance. The tool rejected that combination, and the model invented counts after the error. Automatic mode inference now handles a nonzero tolerance, and a final-answer guard blocks conclusions when there is no successful tool evidence or when the last tool round entirely failed. Separate unit tests reproduce both failure patterns.

After the API correction, the tool-evidence run passed **30/30** in 40.848 seconds. Separate web checks then found incorrect model paraphrases of correct observations. Focused business answers are now rendered directly from computed observations. The final run passed **30/30** in **39.548 seconds**, with all 13 tools exercised, and all three web checks passed assertions on their final displayed wording. One intermediate invalid-column error was corrected on the next tool round after the model received the error observation. The [compact evidence record](thirteen-tool-v1.summary.json) includes per-task outcomes and the initial result. These cases informed development, so they are not an independent held-out benchmark. The scorer does not verify every statement in generated prose.

## Earlier ten-tool suite

```bash
python evaluation/expanded.py --output results/expanded.json
python evaluation/expanded.py --limit 3 --output results/pilot.json
python evaluation/expanded.py --tasks evaluation/group_count_paraphrases.json --output results/paraphrases.json
```

The suite uses a fixed synthetic office fixture plus a five-value outlier fixture. It covers all ten tools, Chinese and English questions, and multi-tool requests. Each task is isolated and limited to three tool rounds by default. Results are checkpointed after each task. Runs are sequential; no concurrency or continuous inference is required.

`expanded_tasks.json` contains the 24 original questions. `group_count_paraphrases.json` contains two questions first introduced after a grouped-text-count failure. Those questions subsequently informed debugging and are now regression cases, not an independent held-out test set.

## What is scored

Each check inspects actual tool observations against fixture facts: counts, means, date ranges, correlations, or report content. A task also requires a nonempty final answer and must not end at a loop guard or tool-round limit. Intermediate tool errors are retained for inspection and may be recovered from.

Equivalent valid computation paths are accepted. For example, counting status values grouped by status yields the same category frequencies as a single-field distribution for this fixture. Scorer revision 2 recognizes that path.

Generated prose accuracy is **not automatically scored**. A correct tool observation does not prove the model explained it faithfully. These small, hand-authored development cases do not establish general reliability, robustness to arbitrary uploads, or independent benchmark performance.

## Observed development history

| Run | Original cases | Additional paraphrases | Finding |
|---|---:|---:|---|
| Initial descriptions | 23/24 | — | Model confused grouped text counts with duplicate checking and stopped on repetition |
| Clarified tool descriptions | 23/24 as originally scored | 1/2 | One original result was correct through an equivalent route; a Chinese category description was used as a literal nonexistent column |
| Field metadata + scorer revision 2 | 24/24 | 2/2 | Original failures resolved on these cases |

The final original-suite run took **27.747 s**, and the two paraphrase cases took **2.427 s** on the development V100. These are single-run timings. Direct per-task summaries and actual covered tools are in [ten-tool-v1.summary.json](ten-tool-v1.summary.json); full execution traces remain server-side outside the source tree.

The model now receives a bounded list of exact column names and types. It receives no sample row values through this metadata. Tool descriptions distinguish redundant duplicates from non-null counts within categories. The underlying statistics still come from the tools.

## Historical baseline

`benchmark.py` and `tasks.json` describe the earlier 20-task, five-tool baseline. Its previous results must not be presented as measurements of the expanded suite. Run each suite with a different result path to preserve evidence.


## Natural-language charts (20 tools)

`chart_tasks.json` contains eight bilingual chart requests with fixed category totals/counts, histogram counts, and daily values. `twenty_tasks.json` adds them to the prior 42 cases. Run `expanded.py --tasks evaluation/twenty_tasks.json --output results/twenty.json`; this remains a synthetic development set. `check_chart_web.py` separately verifies the live Plotly callback, HTML file download and resets. Gradio omits layout-component updates from its client API; callback unit checks cover tab-selection values, while a browser check is still required to verify their visual effect.


## Session-aware web checks

`check_session_web.py` evaluates paired natural-language follow-ups in two languages, restoring an old result and following its branch, fresh-context behavior, dataset/clear resets and separate client sessions. `check_session_report_web.py` verifies report creation after a chart and exact report restoration after a later task. These scripts exercise the session-aware Gradio app directly; public callback output ordering is preserved because history is a server-side State. They do not substitute for browser rendering or demonstrate arbitrary conversational reliability.


## Generic workbook tools (25 + 1)

`check_generic_web.py` covers actual sheet discovery from a blank-cover workbook, header inspection followed by a calculated sum, AND/OR filters, multiple grouping fields, grouped row products, explicit weighted means and division exclusions. It fails with a nonzero exit code if any case fails. Full raw runs stay on the inference server; the compact source-controlled record retains failures and final outcomes.

The earlier domain sales-filter scorer now also accepts a mathematically equivalent `aggregate_rows` result, requiring the actual metric/field, literal completed-status condition, three matched rows and sum 3500. It still rejects dropping conditions, changing the aggregation or counting a different population. This scorer revision is separate from model improvements; previous runs are not relabeled.

# Follow-up questions and session history

> Update: the archive described below is now saved to disk per session; see [PERSISTENT_SESSIONS.md](PERSISTENT_SESSIONS.md). The statements below about in-memory-only storage describe the earlier version.

This update keeps the 20-tool registry and adds per-dataset follow-up context plus a small result archive. It was inspired by [Data Formulator's Data Threads](https://github.com/microsoft/data-formulator), which support iterative questions and alternative analysis paths, and [PandasAI's conversational data analysis](https://github.com/sinaptik-ai/pandas-ai). Their README behavior informed the interaction; no code or packages from those repositories were copied or installed.

## Use it

1. Load **订单示例** and ask `按 region 分组，用 amount 合计画柱状图。`
2. Continue with `改成平均值，其他不变。` The Agent receives the prior tool choices and must make a new tool call for the changed calculation.
3. Open **本次分析记录 · 最近 8 次** to restore an earlier answer, trace and available report download. Its chart is reconstructed from the original tool observation. Restoring does not call the model.
4. A follow-up after restoring an earlier result uses that result as its parent; it does not silently use a later analysis instead.
5. **新问题** clears the active context and displayed result while retaining the archive. Replacing or removing the dataset clears both context and archive atomically.

The archive is limited to eight computed analyses in the current Gradio session. Server-side state expires after an hour of inactivity or is lost on application restart. It is not long-term storage, a cross-session memory, a full chat transcript or a tree visualization. Failed requests without successful tool evidence do not replace the last useful context.

## What the model receives

`src/session_history.py` creates a bounded JSON record from at most two linked turns, up to 768 UTF-8 bytes. It contains short prior questions and successful tool names/arguments. Prior answers, raw rows, observations, report content and report paths are not included. Whole argument records are retained or omitted; oversized strings are not rewritten into incorrect field names.

`src/agent.py` adds this context only when an active prior result exists. No-context requests keep the original message structure. Context is marked as untrusted task history. The current user request controls changes; unchanged chart settings may be reused. Every current numerical conclusion still requires a new tool invocation and its observation. This is bounded task context rather than retrieval-augmented or persistent agent memory.

Archive entries retain full computed answers and traces for restoring the UI. The model receives only the small selection record above. Records are kept in `gr.State`, not a shared global dictionary, and are not sent to external services. The model endpoint remains localhost-only.

## Implementation

- Dataset callbacks return the new frame and empty history in one update, inside the same concurrency group as analysis and restoration.
- `on_session_submit` records the exact submitted question and its computed outputs together.
- `on_restore_analysis` restores server-side history by an opaque entry ID and updates the active parent.
- `on_new_question` resets active context while preserving previous entries.
- State outputs are omitted by Gradio's public client API, preserving the existing three visible `/on_submit` outputs and dataset callback ordering.
- History choices change programmatically; restoration is bound to user input rather than programmatic dropdown updates to avoid a restore/reset loop.

## Page refinements

The centered workbench retains the existing chart/question layout. Text contrast and spacing were adjusted; the header now uses a small code-native chart mark. The result label covers both checks and charts. Computation records have a compact expandable summary showing invocation count and **tool execution time**, not total model latency. Keyboard focus indicators, the history selector and a **新问题** action complete the interaction.

Actual browser verification has now exercised history selection, chart follow-ups, fresh-question resets and data switching, including the client-side event chain. Responsive layouts and a narrow-button fix are recorded in [VISUAL_QA.json](VISUAL_QA.json). The README now uses the current browser screenshot.


## Validation record

On the existing V100/Qwen2.5 baseline, context 4096 and maximum output 256, server checks passed **32 standard-library cases plus 97 dependency-based tests**. The first configuration test caught an unsupported Gradio dropdown parameter; it was removed before the app restart. The final suite passed in 9.00 seconds (with existing framework deprecation warnings). No inference service or global dependency was replaced.

`evaluation/check_session_web.py` passed **5/5 follow-up groups**: Chinese and English category-chart averages, daily-to-monthly line changes, and restoring an earlier region chart after a department chart before continuing from it. The checker also confirmed archive retention on a fresh question, dataset and clear resets, and empty history in a separate client session. These are fixed synthetic development tasks, not a general conversation benchmark.

`evaluation/check_chart_web.py` passed all three chart/download cases on the session-aware app. `evaluation/check_session_report_web.py` generated a complete report after a chart, performed another task, and restored the exact original report text and download. Source fixtures, test scripts and compact evidence are kept in the repository; full live traces stay server-side.

The existing three consistency-tool web checks also passed on the session-aware app, including preview redaction and clear behavior. [Compact evidence](../evaluation/session-history.summary.json) records outcomes and fresh chart values; the original 50-task no-context result remains earlier evidence and was not rerun or relabeled as a new benchmark.

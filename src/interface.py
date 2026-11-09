"""Presentation only: shared visual language and plain-language tool descriptions."""
from __future__ import annotations

from html import escape

import pandas as pd

from .i18n import tr

APP_CSS = """
:root { --ink:#202a3c; --muted:#68758b; --line:#e6e9f0; --accent:#526be4; }
body, .gradio-container { background:#f4f6fa !important; }
.gradio-container { width:100% !important; max-width:1260px !important; margin:0 auto !important; padding:22px 26px 28px !important; box-sizing:border-box !important; color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif !important; }
.gradio-container > main { width:100% !important; max-width:none !important; padding:0 !important; }
.app-header { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:0 2px 20px; }
.brand { display:flex; align-items:center; gap:11px; }
.brand-mark { display:grid; place-items:center; width:33px; height:33px; background:#526be4; border-radius:9px; color:white; font-size:20px; font-weight:650; }
.brand h1 { font-size:21px; letter-spacing:-.6px; font-weight:650; color:#202a3c; margin:0; }
.app-header p { margin:0; font-size:12px; color:#8b95a6; }
#main-tabs { border:0 !important; }
#main-tabs > .tab-nav { border-bottom:1px solid #e1e6ef !important; gap:25px !important; padding:0 2px !important; }
#main-tabs > .tab-nav button { padding:9px 0 13px !important; border-radius:0 !important; font-size:13px !important; font-weight:550 !important; color:#8791a2 !important; border-bottom:2px solid transparent !important; background:transparent !important; }
#main-tabs > .tab-nav button.selected, #main-tabs > .tab-nav button[aria-selected=true] { color:#4e65d7 !important; border-bottom-color:#526be4 !important; }
.tabitem { background:transparent !important; border:0 !important; padding:18px 0 0 !important; }
.data-actions { align-items:center !important; gap:9px !important; background:white !important; padding:12px 14px !important; border:1px solid var(--line) !important; border-radius:11px !important; }
.data-actions > .column { min-height:0 !important; }
#choose-csv { min-height:35px !important; background:#526be4 !important; color:white !important; border:1px solid #526be4 !important; border-radius:7px !important; font-size:12px !important; font-weight:550 !important; padding:7px 16px !important; box-shadow:none !important; }
#choose-csv:hover, #run-check:hover { background:#425bd1 !important; }
.file-status { color:#9aa3b2; font-size:11px; line-height:1.5; overflow-wrap:anywhere; padding-left:5px; }
.file-status strong { color:#455168; font-size:12px; font-weight:550; margin-right:9px; }
.file-status span { white-space:nowrap; }
.file-status em { font-style:normal; font-weight:450; font-size:10px; color:#6680d0; background:#eef2ff; border-radius:4px; padding:2px 5px; margin-left:7px; }
.file-status.failed { color:#b46248; }
.file-status details { margin-top:4px; }
.sample-button { background:transparent !important; color:#7e899c !important; border:0 !important; border-radius:6px !important; min-height:32px !important; padding:5px 8px !important; font-size:11px !important; box-shadow:none !important; }
.sample-button:hover { background:#f1f4fc !important; color:#526be4 !important; }
#clear-file { background:transparent !important; border:0 !important; color:#a5acb9 !important; font-size:11px !important; padding:5px !important; min-height:32px !important; box-shadow:none !important; }
.stat-band { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); background:white; border:1px solid var(--line); border-radius:11px; padding:20px 0; margin:0; }
.stat { padding:0 24px; border-right:1px solid #edf0f5; }
.stat:last-child { border-right:0; }
.stat-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.stat-label { font-size:12px; color:#65738a; }
.stat-value { font-size:30px; font-weight:600; line-height:1; color:#253147; letter-spacing:-.7px; font-variant-numeric:tabular-nums; }
.stat-value.attention { color:#b48149; }
.stat-unit { font-size:11px; color:#748197; margin-top:9px; }
.work-grid { align-items:flex-start !important; gap:18px !important; }
.chart-card, .ask-panel { background:white !important; border:1px solid var(--line) !important; border-radius:12px !important; padding:22px !important; gap:14px !important; box-shadow:0 4px 22px rgba(38,51,84,.035) !important; }
#chart-tabs { border:0 !important; }
#chart-tabs > .tab-nav { border-bottom:1px solid #edf0f6 !important; gap:18px !important; padding:0 !important; }
#chart-tabs > .tab-nav button { background:transparent !important; border-radius:0 !important; padding:6px 0 11px !important; font-size:12px !important; font-weight:550 !important; color:#8a94a5 !important; }
#chart-tabs > .tab-nav button.selected { color:#4156bd !important; border-color:#6b7de0 !important; }
#chart-tabs .tabitem { padding:12px 0 0 !important; }
.chart-caption { font-size:11px; color:#6d7b90; margin-bottom:4px; }
.chart-card .block { border:0 !important; background:transparent !important; box-shadow:none !important; padding:0 !important; }
#distribution-picker { min-height:36px; }
.section-heading { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.section-heading h2 { font-size:16px; font-weight:600; color:#2a354b; margin:0; }
.section-heading span { font-size:10px; color:#a0a9b7; }
#question { background:transparent !important; border:0 !important; padding:0 !important; }
#question textarea { background:#fcfdff !important; border:1px solid #dfe5ef !important; border-radius:8px !important; padding:12px !important; font-size:14px !important; line-height:1.7 !important; color:#415069 !important; box-shadow:none !important; }
#question textarea:focus { border-color:#8c9bea !important; outline:2px solid #edf0ff !important; }
.quick-row { gap:7px !important; justify-content:flex-start !important; }
.quick-button { flex:0 0 auto !important; min-height:31px !important; background:#f5f7fc !important; border:0 !important; border-radius:5px !important; font-size:11px !important; color:#607395 !important; padding:4px 10px !important; box-shadow:none !important; }
.quick-button:hover { background:#eaf0ff !important; color:#526be4 !important; }
#run-check { min-height:37px !important; background:#526be4 !important; border:1px solid #526be4 !important; color:white !important; border-radius:7px !important; font-size:12px !important; font-weight:550 !important; box-shadow:none !important; }
.result-label { margin-top:5px; padding-top:17px; border-top:1px solid #edf0f6; font-size:12px; font-weight:550; color:#60718d; }
#analysis-answer { line-height:1.85; font-size:14px; color:#46536b; max-height:480px; overflow:auto; }
#analysis-answer h2, #analysis-answer h3 { font-size:14px !important; color:#35435d; }
#analysis-answer table { font-size:11px; width:100%; min-width:360px; border-collapse:collapse; }
#analysis-answer th, #analysis-answer td { white-space:nowrap; padding:8px 9px !important; border:1px solid #e5eaf3 !important; }
#analysis-answer th { background:#f7f9fd; color:#5f7290; font-weight:550; }
#download-report { min-height:33px !important; background:#f1f4ff !important; color:#526be4 !important; border:1px solid #e5eafb !important; font-size:11px !important; border-radius:6px !important; box-shadow:none !important; }
#calculation-log { background:transparent !important; border:0 !important; border-top:1px solid #edf0f6 !important; border-radius:0 !important; }
#calculation-log > .label-wrap { color:#8e99ab !important; font-size:11px !important; padding:12px 0 2px !important; }
.catalog-intro { padding:4px 0 18px; }
.catalog-intro h2 { font-size:20px; font-weight:600; color:#263249; margin:0 0 7px; }
.catalog-intro p { color:#8b95a5; font-size:12px; margin:0; }
.catalog-section { margin-bottom:22px; }
.catalog-section > h3 { font-size:11px; color:#7b89a1; font-weight:550; margin:0 0 10px; }
.tool-list { background:white; border:1px solid var(--line); border-radius:11px; padding:0 20px; }
.tool-row { display:grid; grid-template-columns:140px 1.2fr 1.4fr; gap:20px; align-items:center; padding:16px 0; border-bottom:1px solid #edf0f6; }
.tool-row:last-child { border-bottom:0; }
.tool-row h4 { margin:0; color:#41506a; font-size:12px; font-weight:550; }
.tool-row p { margin:0; color:#68758b; font-size:12px; line-height:1.8; }
.tool-example { color:#6f82b5; font-size:11px; line-height:1.8; }
.page-foot { display:flex; justify-content:space-between; gap:16px; border-top:1px solid #e3e8f1; padding-top:14px; margin-top:22px; font-size:10px; color:#a1aab8; }

#main-tabs > .tab-nav { margin-bottom:2px; }
#question textarea::placeholder { color:#a1aabd; }
#analysis-answer { padding:2px 0 5px; }
#analysis-answer strong { color:#33496d; }
#data-preview { border:0 !important; border-top:1px solid #edf0f6 !important; border-radius:0 !important; background:transparent !important; }
#data-preview > .label-wrap { font-size:11px !important; color:#8a98ad !important; padding:12px 0 !important; }
.preview-scroll { overflow-x:auto; border:1px solid #edf0f6; border-radius:7px; }
.preview-table { width:100%; border-collapse:collapse; font-size:11px; text-align:left; white-space:nowrap; }
.preview-table th, .preview-table td { border:1px solid #edf0f6; }
.preview-table th { background:#f8faff; color:#75849b; font-weight:500; padding:9px 11px; }
.preview-table td { padding:9px 11px; color:#53617a; border-top:1px solid #edf0f6; }
.preview-table td.missing, .preview-table td.redacted { color:#a9b0bd; font-style:italic; }
.preview-empty, .execution-empty { font-size:11px; color:#a4aebe; padding:5px 0; }
.execution-list { border:1px solid #e8ecf3; border-radius:8px; padding:0 12px; background:#fcfdff; }
.execution-list summary { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:7px; cursor:pointer; padding:12px 0; font-size:12px; color:#586b87; }
.execution-list summary::after { content:"＋"; color:#7c8ca6; }
.execution-list[open] summary::after { content:"−"; }
.execution-meta { margin-left:auto; font-size:10px; color:#64758e; }
.execution-row { display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid #f0f3f8; font-size:11px; }
.execution-index { color:#b0b9c8; font-variant-numeric:tabular-nums; }
.execution-label { flex:1; color:#697a92; }
.execution-time { font-size:11px; color:#718099; }
.execution-badge { font-size:10px; padding:2px 6px; border-radius:4px; }
.execution-badge.ok { background:#edf6f0; color:#3d7654; }
.execution-badge.error { background:#fff3e9; color:#8b6035; }

.context-hint { color:#66758b; font-size:11px; line-height:1.7; }
.question-heading { align-items:center !important; gap:8px !important; flex-wrap:nowrap !important; }
.question-heading > * { min-width:0 !important; }
.question-heading > .html-container { flex:1; min-width:0; }
#new-question { flex:0 0 68px !important; width:68px !important; min-width:68px !important; white-space:nowrap !important; min-height:32px !important; padding:5px 10px !important; color:#687d9f !important; font-size:11px !important; border:1px solid #e6ebf4 !important; border-radius:6px !important; background:#fafbfe !important; box-shadow:none !important; }
#new-question:hover { background:#eef2fc !important; border-color:#d4ddef !important; }
#session-history { background:transparent !important; border:0 !important; border-top:1px solid #edf0f6 !important; border-radius:0 !important; }
#session-history > .label-wrap { color:#64758f !important; font-size:12px !important; padding:12px 0 !important; }
#session-history .context-hint { padding-top:8px; }
#reference-panel { background:#fafbfe !important; border:1px solid #e7ecf5 !important; border-radius:8px !important; }
#reference-panel > .label-wrap { color:#5b6f91 !important; font-size:12px !important; padding:12px !important; }
.reference-actions { gap:8px !important; padding:0 12px !important; align-items:center !important; }
.reference-upload, .reference-clear { min-height:32px !important; border-radius:6px !important; font-size:11px !important; box-shadow:none !important; }
.reference-upload { background:#edf1ff !important; border:1px solid #dce4fc !important; color:#4b61b8 !important; }
.reference-clear { background:transparent !important; border:1px solid #e5eaf3 !important; color:#6b7b94 !important; }
#reference-panel .context-hint, .reference-ready, .reference-error { padding:8px 12px; font-size:11px; line-height:1.7; overflow-wrap:anywhere; }
.reference-ready { display:flex; gap:7px; flex-wrap:wrap; align-items:center; color:#617390; }
.reference-ready > span { padding:1px 6px; border-radius:4px; background:#e9f0fa; color:#4d6995; }
.reference-ready strong { font-weight:550; }
.reference-ready small { font-size:10px; }
.reference-error { color:#9b603d; }
.artifact-actions { gap:8px !important; flex-wrap:wrap !important; }
.artifact-actions > button { flex:1 1 145px !important; min-width:0 !important; white-space:nowrap !important; }
#download-record { min-height:33px !important; background:#f8fafc !important; color:#58718f !important; border:1px solid #e2e9f3 !important; font-size:11px !important; border-radius:6px !important; box-shadow:none !important; }
.record-file-link { display:flex; align-items:center; justify-content:center; min-height:33px; padding:0 12px; color:#58718f !important; text-decoration:none !important; font-size:11px; }
.record-file-link:hover { background:#edf3fa; }
.record-file-link:focus-visible { outline:2px solid #537cba; outline-offset:2px; }
button:focus-visible, summary:focus-visible { outline:2px solid #879ce4 !important; outline-offset:3px; }
footer { display:none !important; }
@media(max-width:1100px) { .work-grid { flex-direction:column !important; } .chart-card, .ask-panel { width:100% !important; min-width:0 !important; flex:auto !important; } }
@media(max-width:900px) { .work-grid { flex-direction:column !important; } .chart-card, .ask-panel { width:100% !important; min-width:0 !important; flex:auto !important; } .tool-row { grid-template-columns:110px 1fr; } .tool-example { grid-column:2; } .file-info { min-width:140px !important; } }
@media(max-width:560px) { .gradio-container { padding:18px 14px !important; } .app-header { padding-bottom:15px; } .app-header p { display:none; } .data-actions { padding:10px !important; gap:6px !important; } .file-info { min-width:150px !important; } .stat-band { grid-template-columns:repeat(2,minmax(0,1fr)); gap:17px 0; padding:17px 0; } .stat { padding:0 17px; } .stat:nth-child(2) { border-right:0; } .stat-value { font-size:27px; } .chart-card, .ask-panel { padding:16px !important; } .tool-row { grid-template-columns:1fr; gap:6px; padding:15px 0; } .tool-example { grid-column:1; } .page-foot { display:block; line-height:1.9; } .page-foot span { display:block; } }
.session-bar { align-items:center !important; gap:9px !important; margin-bottom:10px !important; flex-wrap:nowrap !important; }
.session-bar .block { border:0 !important; background:transparent !important; box-shadow:none !important; }
#session-picker { flex:0 0 300px !important; min-width:200px; }
#session-picker input, #session-picker .wrap, #session-picker .wrap-inner { background:white !important; color:#2a354b !important; }
#session-picker .wrap { border:1px solid #dfe5ef !important; border-radius:8px !important; }
#new-session { flex:0 0 96px !important; }
.session-bar > .block:last-child { flex:1 1 auto !important; }
#session-manage, #session-manage .block, #session-manage .label-wrap { background:white !important; color:#2a354b !important; }
#session-manage textarea, #session-manage input { background:#fcfdff !important; color:#2a354b !important; }
#session-picker input { font-size:13px !important; font-weight:550 !important; color:#2a354b !important; }
#new-session { background:white !important; color:#4156bd !important; border:1px solid #cfd7f5 !important; box-shadow:none !important; }
.save-status { font-size:11px; color:#8a94a5; line-height:1.5; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; }
.save-status.warn { color:#a2742f; white-space:normal; }
.save-status.error { color:#b46248; white-space:normal; }
#session-manage { margin-bottom:10px !important; }
.delete-warn { font-size:12px; color:#a2523a; background:#fff6f2; border:1px solid #f0d6cc; border-radius:7px; padding:9px 12px; }
@media (max-width:640px) { #session-picker, #new-session { flex:1 1 100% !important; } .session-bar { flex-wrap:wrap !important; } .session-bar > * { min-width:100% !important; } #new-session { min-width:100% !important; } .save-status { white-space:normal; } }
/* ===== Refined, quiet visual system (overrides the rules above) ===== */
:root, .dark, body.dark {
  color-scheme: light;
  --ink:#1d1d1f; --muted:#6e6e73; --faint:#86868b; --line:#e8e8ed; --accent:#0071e3; --accent-hover:#0077ed; --surface:#ffffff; --wash:#f5f5f7;
  --body-background-fill:#fbfbfd; --background-fill-primary:#ffffff; --background-fill-secondary:#f5f5f7;
  --block-background-fill:#ffffff; --block-border-color:transparent; --border-color-primary:#e8e8ed; --border-color-accent:#0071e3;
  --body-text-color:#1d1d1f; --body-text-color-subdued:#6e6e73; --block-label-text-color:#6e6e73; --block-title-text-color:#1d1d1f;
  --input-background-fill:#f5f5f7; --input-background-fill-focus:#ffffff; --input-border-color:transparent; --input-border-color-focus:#0071e3;
  --panel-background-fill:#ffffff; --table-even-background-fill:#ffffff; --table-odd-background-fill:#fafafc;
  --button-secondary-background-fill:#f5f5f7; --button-secondary-text-color:#0066cc; --button-secondary-border-color:transparent;
  --shadow-drop:none; --shadow-drop-lg:none; --color-accent-soft:#e8f1fd;
}
body, .gradio-container { background:#fbfbfd !important; color:var(--ink) !important;
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','SF Pro Text','Helvetica Neue','PingFang SC','Microsoft YaHei',sans-serif !important;
  -webkit-font-smoothing:antialiased; letter-spacing:-.011em; }
.gradio-container { max-width:1120px !important; padding:0 28px 48px !important; }

/* hero */
.hero { text-align:center; padding:72px 0 44px; }
.hero h1 { font-size:clamp(40px,7vw,64px); line-height:1.05; font-weight:650; letter-spacing:-.035em; margin:0; color:#1d1d1f; }
.hero .lead { font-size:clamp(18px,2.6vw,24px); line-height:1.35; font-weight:500; letter-spacing:-.02em; color:#1d1d1f; margin:16px 0 0; }
.hero .sub { display:block; font-size:15px; color:#6e6e73; margin-top:10px; letter-spacing:-.01em; }
.app-header { display:none !important; }
.hero { position:relative; }
.lang-switch { position:absolute; top:22px; right:0; font-size:13px; color:#0066cc !important; text-decoration:none; padding:5px 12px; border-radius:980px; background:#f5f5f7; }
.lang-switch:hover { background:#ebebf0; }

/* tabs */
#main-tabs > .tab-nav { justify-content:center !important; border-bottom:1px solid var(--line) !important; gap:34px !important; padding:0 !important; margin-bottom:6px !important; }
#main-tabs > .tab-nav button { font-size:14px !important; font-weight:500 !important; color:#6e6e73 !important; padding:12px 0 !important; border-bottom:2px solid transparent !important; }
#main-tabs > .tab-nav button.selected, #main-tabs > .tab-nav button[aria-selected=true] { color:#1d1d1f !important; border-bottom-color:#1d1d1f !important; }
.tabitem { padding:28px 0 0 !important; }

/* generic surface language */
.data-actions, .chart-card, .ask-panel, .stat-band, .tool-list { background:#fff !important; border:0 !important; border-radius:22px !important; box-shadow:0 1px 2px rgba(0,0,0,.03), 0 8px 30px rgba(0,0,0,.04) !important; }
.chart-card, .ask-panel { padding:30px !important; gap:18px !important; }
.work-grid { gap:24px !important; margin-top:24px !important; }
.data-actions { padding:16px 22px !important; gap:14px !important; margin-top:6px !important; }
.block, .form { box-shadow:none !important; }
.gr-group, .gr-form { background:transparent !important; border:0 !important; }

/* buttons: one blue pill, everything else quiet */
#choose-csv, #run-check { background:var(--accent) !important; border:0 !important; color:#fff !important; border-radius:980px !important; font-size:14px !important; font-weight:500 !important; padding:10px 22px !important; min-height:40px !important; letter-spacing:-.01em; transition:background .2s ease; }
#choose-csv:hover, #run-check:hover { background:var(--accent-hover) !important; }
#run-check { width:100%; min-height:46px !important; font-size:15px !important; }
.sample-button, .quick-button, #new-question, .reference-clear, #new-session, #rename-session, #delete-session, #delete-no, .reference-upload, #download-report, #download-record, #download-table, #download-script, #clear-file {
  background:#f5f5f7 !important; color:#0066cc !important; border:0 !important; border-radius:980px !important; font-size:13px !important; font-weight:450 !important; min-height:34px !important; padding:6px 16px !important; box-shadow:none !important; transition:background .2s ease; }
.sample-button:hover, .quick-button:hover, #new-question:hover, .reference-clear:hover, #new-session:hover, #rename-session:hover, #delete-no:hover, .reference-upload:hover, #download-report:hover, #clear-file:hover { background:#ebebf0 !important; color:#0066cc !important; }
#clear-file { color:#6e6e73 !important; background:transparent !important; white-space:nowrap !important; flex:0 0 auto !important; min-width:64px !important; width:auto !important; }
#delete-session, #delete-yes { color:#d70015 !important; }
#delete-yes { background:#d70015 !important; color:#fff !important; border-radius:980px !important; border:0 !important; }
.quick-button { color:#424245 !important; }
.question-heading { margin-bottom:2px; }

/* text fields */
#question textarea, #session-name input, #session-name textarea, .gradio-container input[type=number], .gradio-container textarea { background:#f5f5f7 !important; border:1px solid transparent !important; border-radius:14px !important; font-size:16px !important; line-height:1.6 !important; color:#1d1d1f !important; padding:14px 16px !important; box-shadow:none !important; transition:border-color .2s, background .2s; }
#question textarea:focus, #session-name input:focus, .gradio-container textarea:focus { background:#fff !important; border-color:var(--accent) !important; outline:3px solid rgba(0,113,227,.15) !important; }
#question textarea::placeholder { color:#86868b !important; }
.session-bar { margin:0 0 20px !important; justify-content:center !important; }
#session-picker { flex:0 0 340px !important; }
#session-picker .wrap { background:#fff !important; border:1px solid var(--line) !important; border-radius:980px !important; box-shadow:none !important; padding-left:8px !important; }
#session-picker input { font-size:14px !important; font-weight:500 !important; color:#1d1d1f !important; background:transparent !important; }
.session-bar > .block:last-child { flex:0 1 auto !important; }
.save-status { font-size:12px; color:#86868b; }
.save-status.warn { color:#b25000; } .save-status.error { color:#d70015; }
.delete-warn { background:#fff5f5; border:0; color:#b3261e; border-radius:14px; padding:12px 16px; font-size:13px; }
#session-manage, #sample-files, #import-settings, #reference-panel, #data-preview, #data-profile, #session-history, #calculation-log { background:transparent !important; border:0 !important; border-top:1px solid var(--line) !important; border-radius:0 !important; }
#session-manage, #sample-files, #import-settings { background:#fff !important; border-radius:18px !important; border:0 !important; box-shadow:0 1px 2px rgba(0,0,0,.03), 0 6px 22px rgba(0,0,0,.035) !important; margin:12px 0 !important; padding:2px 10px !important; }
#session-manage > .label-wrap, #sample-files > .label-wrap, #import-settings > .label-wrap, #reference-panel > .label-wrap, #data-preview > .label-wrap, #data-profile > .label-wrap, #session-history > .label-wrap, #calculation-log > .label-wrap { font-size:14px !important; font-weight:500 !important; color:#1d1d1f !important; padding:14px 6px !important; background:transparent !important; }
#session-manage .block, #sample-files .block { background:transparent !important; }

/* file info + stats */
.file-status { font-size:13px; color:#6e6e73; padding-left:2px; }
.file-status strong { font-size:15px; font-weight:600; color:#1d1d1f; }
.file-status em { background:#e8f1fd; color:#0066cc; border-radius:980px; padding:2px 9px; font-size:11px; }
.file-status.failed { color:#b25000; }
.stat-band { padding:34px 0 !important; margin-top:20px !important; }
.stat { border-right:1px solid var(--line) !important; padding:0 32px !important; text-align:left; }
.stat-label { font-size:13px !important; color:#6e6e73 !important; font-weight:500; }
.stat-value { font-size:48px !important; font-weight:600 !important; letter-spacing:-.04em !important; color:#1d1d1f !important; line-height:1.05 !important; margin-top:4px; }
.stat-value.attention { color:#bf4800 !important; }
.stat-unit { font-size:12px !important; color:#86868b !important; margin-top:10px !important; }

/* chart tabs, answer, tables */
#chart-tabs > .tab-nav { border-bottom:0 !important; gap:6px !important; background:#f5f5f7 !important; border-radius:980px !important; padding:4px !important; display:inline-flex !important; width:auto !important; }
#chart-tabs > .tab-nav button { border-radius:980px !important; padding:7px 16px !important; font-size:13px !important; font-weight:500 !important; color:#6e6e73 !important; border:0 !important; }
#chart-tabs > .tab-nav button.selected { background:#fff !important; color:#1d1d1f !important; box-shadow:0 1px 3px rgba(0,0,0,.1) !important; }
#chart-tabs .tabitem { padding:18px 0 0 !important; }
.section-heading h2 { font-size:24px !important; font-weight:650 !important; letter-spacing:-.025em !important; color:#1d1d1f !important; }
.result-label { border-top:1px solid var(--line) !important; color:#6e6e73 !important; font-size:13px !important; font-weight:500; padding-top:20px !important; margin-top:8px !important; }
#analysis-answer { font-size:16px !important; line-height:1.7 !important; color:#1d1d1f !important; }
#analysis-answer th { background:#fafafc !important; color:#6e6e73 !important; }
#analysis-answer th, #analysis-answer td { border-color:var(--line) !important; font-size:13px; }
.preview-scroll { border:1px solid var(--line) !important; border-radius:14px !important; }
.preview-table th { background:#fafafc !important; color:#6e6e73 !important; } .preview-table td { color:#1d1d1f !important; }
.preview-table th, .preview-table td { border-color:#f0f0f3 !important; font-size:12px; }
.execution-list { background:#fafafc !important; border:0 !important; border-radius:14px !important; padding:0 16px !important; }
.execution-list summary { font-size:13px !important; color:#424245 !important; }
.context-hint, .chart-caption { font-size:13px !important; color:#86868b !important; line-height:1.6 !important; }
.catalog-intro h2 { font-size:32px !important; font-weight:650 !important; letter-spacing:-.03em !important; color:#1d1d1f !important; }
.catalog-intro p { font-size:15px !important; color:#6e6e73 !important; }
.catalog-section > h3 { font-size:13px !important; color:#6e6e73 !important; font-weight:600 !important; }
.tool-list { padding:0 28px !important; } .tool-row { border-color:var(--line) !important; } .tool-row h4 { font-size:14px !important; color:#1d1d1f !important; }
.tool-row p { font-size:13px !important; color:#6e6e73 !important; } .tool-example { color:#0066cc !important; }
.reference-ready > span { background:#e8f1fd !important; color:#0066cc !important; border-radius:980px !important; padding:2px 10px !important; }
.page-foot { border-top:1px solid var(--line) !important; margin-top:56px !important; padding-top:20px !important; font-size:12px !important; color:#86868b !important; justify-content:center !important; gap:28px !important; }
.grounding { font-size:12px; line-height:1.6; padding:10px 0 12px; color:#86868b; }
.grounding.warn { color:#b25000; }
.grounding.ok { color:#1d7f3f; }
.run-progress { padding:6px 0; color:#1d1d1f; }
.run-progress strong { font-weight:600; font-size:15px; margin-right:10px; }
.run-progress small { color:#86868b; font-size:12px; }
.run-progress ul { list-style:none; margin:10px 0 0; padding:0; font-size:13px; line-height:1.9; color:#424245; }
.run-progress li span { display:inline-block; width:22px; color:#86868b; }
.run-progress li.ok span { color:#1d7f3f; }
.run-progress li.bad span { color:#b25000; }
.run-progress li.run { color:#86868b; }
.model-notice { background:#fff8ec; border-radius:16px; padding:14px 18px; margin:0 0 16px; font-size:13px; line-height:1.65; color:#6e4a00; }
.model-notice strong { display:block; font-size:14px; font-weight:600; color:#8a5300; margin-bottom:2px; }
.model-notice code { background:rgba(0,0,0,.05); border-radius:6px; padding:1px 6px; font-size:12px; white-space:nowrap; }
.artifact-actions { gap:8px !important; flex-wrap:wrap !important; margin-top:6px !important; }
.artifact-actions > * { flex:0 0 auto !important; width:auto !important; min-width:0 !important; }
/* secondary options read as quiet disclosure rows, not as more cards */
#session-manage, #sample-files, #import-settings { background:transparent !important; box-shadow:none !important; border-radius:0 !important;
  border:0 !important; border-bottom:1px solid var(--line) !important; margin:0 !important; padding:0 4px !important; }
#session-manage { border-top:0 !important; margin-bottom:18px !important; border-bottom:0 !important; }
#session-manage > .label-wrap { justify-content:center !important; gap:6px; color:#0066cc !important; font-size:13px !important; padding:4px 0 !important; }
#session-manage > .label-wrap .icon { transform:scale(.8); color:#0066cc !important; }
#sample-files { border-top:1px solid var(--line) !important; margin-top:18px !important; }
#sample-files > .label-wrap, #import-settings > .label-wrap { font-size:13px !important; color:#424245 !important; padding:13px 2px !important; }
.session-bar { justify-content:center !important; align-items:center !important; flex-wrap:wrap !important; gap:10px !important; margin-bottom:6px !important; }
.session-bar > * { flex-grow:0 !important; }
#save-status { flex:1 1 100% !important; text-align:center; }
.sample-button { white-space:nowrap !important; min-width:88px !important; }
#choose-csv, #new-session, #new-question, #rename-session, #delete-session, .reference-upload, .reference-clear { white-space:nowrap !important; width:auto !important; flex:0 0 auto !important; }
#choose-csv { min-width:120px !important; } #new-session { min-width:96px !important; }
#domain-examples { min-width:150px !important; }
#domain-examples .wrap { background:#f5f5f7 !important; border:0 !important; border-radius:980px !important; }
#data-profile .preview-scroll { margin:0 6px 10px; }
button:focus-visible, summary:focus-visible { outline:3px solid rgba(0,113,227,.35) !important; outline-offset:2px; }
#main-tabs > .tab-wrapper .tab-container { justify-content:center !important; gap:36px !important; height:auto !important; }
#main-tabs > .tab-wrapper .tab-container::after { background:var(--line) !important; height:1px !important; }
#main-tabs > .tab-wrapper .tab-container button { font-size:15px !important; font-weight:500 !important; color:#6e6e73 !important; padding:12px 2px !important; background:transparent !important; }
#main-tabs > .tab-wrapper .tab-container button.selected { color:#1d1d1f !important; }
#main-tabs > .tab-wrapper .tab-container button.selected::after { background:#1d1d1f !important; height:2px !important; }
#chart-tabs > .tab-wrapper { margin-bottom:6px; }
#chart-tabs > .tab-wrapper .tab-container { display:inline-flex !important; width:auto !important; height:auto !important; background:#f5f5f7 !important; border-radius:980px !important; padding:4px !important; gap:2px !important; }
#chart-tabs > .tab-wrapper .tab-container::after { display:none !important; }
#chart-tabs > .tab-wrapper .tab-container button { border-radius:980px !important; padding:7px 18px !important; font-size:13px !important; font-weight:500 !important; color:#6e6e73 !important; background:transparent !important; border:0 !important; }
#chart-tabs > .tab-wrapper .tab-container button.selected { background:#fff !important; color:#1d1d1f !important; box-shadow:0 1px 3px rgba(0,0,0,.12) !important; }
#chart-tabs > .tab-wrapper .tab-container button.selected::after, #chart-tabs > .tab-wrapper .tab-container button::after { display:none !important; }

@media (max-width:640px) {
  .gradio-container { padding:0 16px 36px !important; }
  .hero { padding:44px 0 28px; }
  .chart-card, .ask-panel { padding:20px !important; border-radius:18px !important; }
  .stat-value { font-size:36px !important; } .stat { padding:0 18px !important; }
  #session-picker { flex:1 1 100% !important; }
  .session-bar { justify-content:flex-start !important; }
}
"""

def header_html(lang='zh') -> str:
    """Hero plus a quiet language switch (relative links work behind a path prefix)."""
    switch = ('<a class="lang-switch" href="../" hreflang="zh">中文</a>' if lang == 'en'
              else '<a class="lang-switch" href="en/" hreflang="en">English</a>')
    return ('<div class="hero">' + switch + '<h1>DataAudit</h1><p class="lead">' + tr('读懂每一张表格。') + '</p>'
            '<span class="sub">' + tr('用日常的话检查、计算、绘图，每一步都有据可查。') + '</span></div>')


HEADER = header_html()


def file_status(filename: str | None = None, rows: int = 0, error: str | None = None, sample: bool = False) -> str:
    if error:
        return '<div class="file-status failed">' + tr('读取失败') + '<details><summary>' + tr('查看原因') + '</summary>' + escape(error) + '</details></div>'
    if filename:
        badge = '<em>' + tr('示例') + '</em>' if sample else ''
        return f'<div class="file-status"><strong>{escape(filename)}{badge}</strong><span>' + tr('{n} 行', n=f'{rows:,}') + '</span></div>'
    return '<div class="file-status">' + tr('还没有选择文件') + '</div>'


def overview_html(frame: pd.DataFrame | None = None) -> str:
    values = ['—'] * 4 if frame is None else [f'{len(frame):,}', f'{len(frame.columns):,}',
                                             f'{int(frame.isna().sum().sum()):,}', f'{int(frame.duplicated().sum()):,}']
    missing = int(frame.isna().sum().sum()) if frame is not None else 0
    duplicates = int(frame.duplicated().sum()) if frame is not None else 0
    units = [tr('数据行'), tr('字段'), tr('占全部单元格 {p}', p=f'{missing / frame.size:.1%}') if frame is not None and frame.size else tr('按单元格计数'), tr('不含第一条记录')]
    labels = [tr('行数'), tr('列数'), tr('空白单元格'), tr('重复行')]
    cards = ''
    for index, (label, value, unit) in enumerate(zip(labels, values, units)):
        attention = ' attention' if (index == 2 and missing) or (index == 3 and duplicates) else ''
        cards += f'<div class="stat"><div class="stat-top"><span class="stat-label">{label}</span></div><div class="stat-value{attention}">{value}</div><div class="stat-unit">{unit}</div></div>'
    return '<div class="stat-band">' + cards + '</div>'



def tools_catalog() -> str:
    groups = [
        ('任意表格都能用', [
            ('工作表列表','读取上传文件的真实工作表名，不要求固定名称。','这个文件里有哪些工作表？'),
            ('表头位置','查看前几行的结构，帮助确定列名在哪一行。','先看看这个工作表的表头在哪。'),
            ('按条件查行','支持多个条件、AND/OR、选列与排序。','找出同时满足这两个条件的记录。'),
            ('多字段汇总','按最多三个字段分组，筛选后计算数量或数值。','按这两列分组，统计记录数和均值。'),
            ('逐行计算','计算加减乘除、均值或明确权重，再按组汇总。','把这两列逐行相乘，再按指定字段求和。')]),
        ('先看整体', [
            ('表格结构', '看行数、列名和字段类型。', '这份表有哪些字段？'),
            ('空值检查', '按列统计空白记录，看看缺在哪里。', '哪些列的空值最多？'),
            ('重复记录', '统计整行重复，或按指定字段查重。', '有多少完全重复的记录？'),
            ('数值和类别', '看均值、中位数，或者各类别的数量。', 'amount 的平均值是多少？'),
            ('主键检查', '同时检查键值缺失、重复和组合键。', 'order_id 能作为主键吗？')]),
        ('找不一致的地方', [
            ('格式检查', '找出数字和文字混在一起的列。', '哪些列的格式不太一致？'),
            ('偏离较大的数值', '用 IQR 方法筛出值得再看一眼的值。', 'amount 里有没有特别高的值？'),
            ('范围检查', '按你给出的上下限检查，不擅自设标准。', 'amount 是否都在 0 到 250 之间？'),
            ('两列对账', '逐行核对，支持数值误差和缺失值统计。', '两列金额允许差 0.01，有多少不一致？'),
            ('文字格式', '检查纯空白、首尾空格和大小写写法。', 'status 有没有大小写和空格混用？'),
            ('条件必填', '按你指定的条件检查必填字段。', 'completed 订单的金额和实收是否都填写？'),
            ('日期先后', '核对开始和结束日期的顺序。', 'ship_date 有没有早于 order_date？'),
            ('类别检查', '检查取值是否都在你给出的允许列表里。', 'status 只能是 completed 或 pending，哪些值不符合？')]),
        ('做统计，整理结果', [
            ('分组统计', '按地区、部门等类别计算总额、均值或数量。', '哪个 region 的平均 amount 最高？'),
            ('相关性', '看看两个数值字段是否一起变化。', '哪些数值列的相关性最高？'),
            ('日期检查', '查看日期范围和无法识别的日期。', 'order_date 里有无效日期吗？'),
            ('按时间汇总', '按天、周或月计算总额、均值和数量。', '每个月的 amount 总额是多少？'),
            ('检查报告', '整理成一份可下载的报告。', '帮我生成一份检查报告。'),
            ('条件统计', '先筛选记录，再计算数量、总额或均值。', '只看 completed 的订单，amount 总额是多少？'),
            ('生成图表', '用一句话画柱状图、直方图或日期折线图，可下载。', '按 region 分组，用 amount 合计画柱状图。')]),
        ('对照两份表', [
            ('参考表对照', '先选参考表，再比较字段、缺失率和分布差异。', '和参考表比，amount 的缺失率和均值变了吗？')]),
    ]
    html = '<div class="catalog-intro"><h2>' + tr('工具库') + '</h2><p>' + tr('26 项检查、统计、绘图与对照工具。直接描述问题即可。') + '</p></div>'
    for heading, tools in groups:
        html += f'<section class="catalog-section"><h3>{tr(heading)}</h3><div class="tool-list">'
        for title, description, example in tools:
            html += (f'<article class="tool-row"><h4>{tr(title)}</h4><p>{tr(description)}</p>'
                     f'<div class="tool-example">{tr("例如：")}{tr(example)}</div></article>')
        html += '</div></section>'
    return html

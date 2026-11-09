# Qwen3 live trial on the V100

This record describes the **19-tool** iteration and its 42-task suite, before the natural-language chart update. It is retained as historical model-comparison evidence, not a test of the later 20-tool registry.

The candidate has now been downloaded, verified, loaded on the V100, and exercised through the same 42-task development suite. **The web app retains Qwen2.5-7B-Instruct Q4_K_M as its default.** Qwen3 remains a separate localhost-only trial service at port 8081.

## Recorded outcomes

| Configuration | Context / output budget | Evidence tasks | Total time, one run | Observed per-process GPU memory |
|---|---:|---:|---:|---:|
| Qwen2.5-7B-Instruct Q4_K_M, temperature 0 | 4096 / 256 | 42/42 | 62.353 s | 5506 MiB |
| Qwen3-4B-Instruct-2507 Q4_K_M, temperature .7 / top-p .8 | 4096 / 256 | 40/42 | 56.078 s | 3900 MiB |
| Same Qwen3, larger budgets | 8192 / 512 | 42/42 | 60.540 s | 4908 MiB |

These are individual, sequential development runs on synthetic data, not independent benchmarks or latency distributions. Sampling differed by model, following the candidate model card guidance. The larger-budget candidate is a different configuration; its result is not an equal-budget architecture comparison. GPU memory numbers are point observations, not peak measurements. The existing model stayed resident throughout; only one model was being evaluated at a time.

The [compact per-task record](../evaluation/nineteen-model-trial.summary.json) contains all three outcomes, trial limits, errors and web checks. Full raw traces remain server-side outside the source tree. The comparison helper rejects different known context/output budgets rather than ranking those runs as equivalent.

## What failed and what changed

The equal-budget Qwen3 run failed only the English and Chinese report requests. Server logs showed each affected generation reaching the 256-token cap before a complete tool call could be parsed, producing HTTP 500 JSON-argument parsing errors.

A targeted probe kept context at 4096 and raised output to 512. Those requests progressed further but failed with HTTP 400 because their next prompts required 5153 and 5449 tokens. Thus simply raising the output limit did not solve the full report loop.

Only the candidate service was restarted with 8192 context. Both report probes then passed, followed by the full 42/42 candidate run with output capped at 512. The default app/model configuration was not modified. The original 40/42 and failed intermediate probes are preserved; they were not overwritten with the successful run.

The evidence supports Qwen3 as a viable optional backend with this larger configuration. It does not establish a worthwhile default-model improvement: the existing model passed all cases at a smaller context/output budget, and the one-run timing difference is small. Keep the baseline for the demo and retain the candidate for further evaluation. Qwen3-8B was considered from official specifications but was **not downloaded or tested**.

## Model provenance and placement

- Candidate: `bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF` (community quantization of the official Qwen model).
- Revision: `ae44f08e1392f39c0e474af10c3ff8355c8b6688`.
- File: `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2,497,280,736 bytes.
- SHA-256: `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e`.
- Download went directly to the server through an available mirror after the server's upstream connection timed out. The SHA-256 came from the original repository metadata and was verified before loading. No model weights were stored on the Mac.
- Candidate launcher requires an explicit GPU UUID, validates the checksum, binds localhost, enables GPU layers/Jinja, and uses one slot. Flash Attention is disabled for this V100 trial.
- llama.cpp reports `0.9.0-dev (build 0, commit unknown)`. Both models used that binary; the unknown commit is a reproducibility limitation.
- A normal English generation request passed in 1.028 seconds for a 31-token response. This is an individual API smoke check, not a sustained tokens-per-second claim.

The default service on 8080 remained the original running process. The candidate was measured at 3900 MiB with 4096 context and 4908 MiB with 8192 context, while the original process used 5506 MiB. This confirms that the candidate used GPU memory rather than running exclusively on CPU.

## Reproduce without changing the app

Run these from the source checkout **on the server**, with the isolated environment and model files already available. Do not replace the application's `.env` merely to run an evaluation.

```bash
# Candidate service: foreground process; use a process manager/nohup if desired.
.venv/bin/python scripts/run_candidate_model.py \
  --server "$DATAAUDIT_ROOT/llama.cpp/build/bin/llama-server" \
  --model "$DATAAUDIT_ROOT/models/qwen3-4b/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
  --sha256 2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e \
  --gpu-uuid "$GPU_UUID" --context 8192

# Baseline: existing endpoint, app configuration unchanged.
.venv/bin/python evaluation/expanded.py --tasks evaluation/nineteen_tasks.json --output results/baseline-19.json

# Candidate: settings apply only to this evaluation subprocess.
.venv/bin/python evaluation/run_profile.py \
  --profile configs/qwen3-4b-8192.env.example evaluation/expanded.py \
  --tasks evaluation/nineteen_tasks.json --output results/qwen3-4b-8192.json
```

The candidate profile uses temperature .7/top-p .8 and 512 output tokens. `configs/qwen3-4b.env.example` records the initial 256-token trial profile, but a request profile cannot set a server's context allocation: make sure the candidate's launch configuration matches the intended experiment. `configs/qwen3-8b.env.example` remains untested.

For same-budget reports, `evaluation/compare_models.py` compares pass counts, median/mean times and failure IDs; both reports must use the same prompts, task-file digest, round budget, and matching `runtime_limits` when present. The live records were annotated with their actual command/environment budgets after completion without changing task times or outcomes. Reports lacking runtime-limit metadata cannot establish equal server budgets.

## Sources

- [Official Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): non-thinking-only behavior, tool use, supported local runtimes and sampling guidance.
- [Selected community GGUF repository](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/tree/main): the quantization actually tested.
- [Official Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B) and [GGUF files](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/main): specification review only; no 8B trial is claimed.
- [llama.cpp function-calling documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md): Jinja-enabled tool support and template-specific behavior.

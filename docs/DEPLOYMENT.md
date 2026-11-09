# 部署

## 在一台新 GPU 服务器上从零部署

开发用的服务器关闭后，用下面的步骤在新机器上恢复同样的环境。只想接在线 API（DeepSeek、通义等）时，
跳过第 2、3 步，在 `.env` 里填好接口即可，不需要 GPU。

开发环境参考：Tesla V100 16 GB，驱动 530，Python 3.12（项目 venv），llama.cpp 自行编译（CUDA 架构 70）。

**1. 代码和 Python 环境**

```bash
export DATAAUDIT_ROOT=/hy-tmp/dataaudit-agent      # 换成你的数据盘目录
mkdir -p "$DATAAUDIT_ROOT" && cd "$DATAAUDIT_ROOT"
git clone <仓库地址> dataaudit-agent && cd dataaudit-agent
python3 -m venv .venv
.venv/bin/pip install -r requirements-tested.txt   # 开发时验证过的版本；也可用 requirements.txt
cp .env.example .env                               # 默认指向本机 127.0.0.1:8080 的模型服务
```

**2. 模型文件**

需要 Qwen2.5-7B-Instruct 的 Q4_K_M GGUF，保存为
`$DATAAUDIT_ROOT/models/qwen2.5-7b-instruct-q4_K_M.gguf`（约 4.7 GB）。
可从官方仓库 [Qwen/Qwen2.5-7B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) 下载
（官方 q4_k_m 是分卷文件，需要用 llama.cpp 的 `llama-gguf-split --merge` 合并成一个文件）。

开发时使用的文件 SHA-256 为
`2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730`，但当时没有记录下载来源，
新下载的文件校验值可能不同；只要是同一模型、同一量化，行为应当接近，但上面的评测结果需要重跑确认。

**3. 编译 llama.cpp 并启动模型**

```bash
cd "$DATAAUDIT_ROOT" && git clone https://github.com/ggml-org/llama.cpp
cd dataaudit-agent && .venv/bin/pip install -r build-requirements.txt
bash scripts/build_model_server.sh                 # 按 V100 写的 CUDA 架构 70；别的显卡改 CMAKE_CUDA_ARCHITECTURES
bash scripts/start_model.sh                        # 127.0.0.1:8080，别名 qwen2.5-7b-instruct
```

开发时的 llama.cpp 版本没有记录提交号（版本输出为 0.9.0-dev）；新版本若工具调用格式有变化，
用 `python -m src.model_check` 检查即可发现。

**4. 检查并启动网页**

```bash
.venv/bin/python -m src.model_check                # 应全部显示 ✓
.venv/bin/python -m pytest -q                      # 可选：自动测试，不需要模型
bash scripts/start_app.sh                          # 127.0.0.1:7860
```

在自己电脑上用 SSH 端口转发访问：`ssh -p <端口> -L 7860:127.0.0.1:7860 <用户>@<服务器>`，然后打开
http://127.0.0.1:7860 。会话和上传文件保存在 `dataaudit-agent/data/`，换服务器时如需保留，单独拷贝这个目录。

---

## Reference (English)

The web UI and model API are separate processes. The current development deployment uses a Tesla V100 16 GB with Qwen2.5-7B-Instruct Q4_K_M served by llama.cpp. Model weights, llama.cpp binaries, and Python packages stay on the server.

## Directory layout

The helper scripts use this layout and read `DATAAUDIT_ROOT`:

```text
$DATAAUDIT_ROOT/
  dataaudit-agent/              # source checkout, .env, .venv
  models/qwen2.5-7b-instruct-q4_K_M.gguf
  llama.cpp/build/bin/llama-server
  logs/
  gradio-app.pid
  llama-server.pid
```

The scripts default to `DATAAUDIT_ROOT=/hy-tmp/dataaudit-agent` (the data disk on the rented GPU server used during development). Set an absolute `DATAAUDIT_ROOT` when using another location. The application itself can also run from any checkout using `python app.py`.

## Python environment

```bash
cd "$DATAAUDIT_ROOT/dataaudit-agent"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-tested.txt
cp .env.example .env
```

Install `build-requirements.txt` separately if compiling llama.cpp. `scripts/build_model_server.sh` targets CUDA architecture 70 for this V100 deployment. Use an existing compatible model server when available. Record the llama.cpp commit and GGUF checksum in deployment notes; these are not pinned by the Python dependency snapshot.

## Start and access

```bash
export DATAAUDIT_ROOT=/hy-tmp/dataaudit-agent
# Choose a specific allocated GPU UUID from nvidia-smi -L when needed.
# export CUDA_VISIBLE_DEVICES=GPU-...
bash scripts/start_model.sh
bash scripts/start_app.sh
```

The model binds to `127.0.0.1:8080`, with context 4096, parallelism 1, alias `qwen2.5-7b-instruct`, and tool templates enabled by `--jinja`. The app binds to `127.0.0.1:7860` with one queued request at a time. `local` is a development API placeholder, not an internet-facing authentication scheme.

From the client machine:

```bash
ssh -p "$SSH_PORT" -L 7860:127.0.0.1:7860 "$SSH_USER@$SSH_HOST"
```

Open `http://127.0.0.1:7860`. Do not put SSH credentials or private CSVs in the repository.

## Manage processes

```bash
bash scripts/stop_app.sh
bash scripts/start_app.sh
# Stop the model only when intentionally shutting down inference:
bash scripts/stop_model.sh
```

Changing Python application code requires restarting the app. The model service can stay loaded throughout. These scripts launch detached processes; they do not provide automatic crash recovery or survive a server reboot.

## Reports and checks

`DATAAUDIT_REPORT_DIR` controls web report storage; its default is `outputs/reports` inside the checkout, which is ignored by Git. Report files use random names. The app's execution preview is shortened while the downloadable Markdown is preserved separately. Reports include aggregates and column names. Avoid processing confidential datasets on shared deployments without adding access control and a retention policy appropriate to those datasets.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m src.cli examples/office_orders.csv --report outputs/demo-report.md
```

Default tests are CPU-only. To evaluate real tool selection use `evaluation/benchmark.py`; older five-tool benchmark results do not establish ten-tool reliability. Record failures and the exact model/server versions when publishing new results.


## Optional Qwen3 trial service

The development server also has a separate localhost:8081 candidate. It does not replace the app's localhost:8080 baseline. The verified model provenance, launch command, context/output settings and comparison outcomes are documented in [MODEL_COMPARISON.md](MODEL_COMPARISON.md). Use `scripts/run_candidate_model.py` with an explicit model path, SHA-256 and allocated GPU UUID. The launcher refuses the app/baseline ports, validates the file before loading, and changes no other model process.

Model weights, download cache and process logs stay server-side. The Mac source checkout contains only code, fixtures, documentation and compact evaluation summaries. Both services may stay resident, but inference is request-driven.


## Current rented-server layout

The validated runtime uses `DATAAUDIT_ROOT=/hy-tmp/dataaudit-agent`, with the checkout and isolated `.venv` at `/hy-tmp/dataaudit-agent/dataaudit-agent`. Set that root when using the portable scripts in this repository; their default home-directory layout is for a new installation. The baseline process was left running during this update. 

```bash
export DATAAUDIT_ROOT=/hy-tmp/dataaudit-agent
cd "$DATAAUDIT_ROOT/dataaudit-agent"
# Application restart only; keeps both model services loaded.
bash scripts/stop_app.sh
bash scripts/start_app.sh
```

For an intentional candidate shutdown, read its PID from `$DATAAUDIT_ROOT/qwen3-candidate.pid`, verify that `/proc/<PID>/cmdline` names the Qwen3 candidate and port 8081, and send SIGTERM only to that process. Relaunch with the verified command in [MODEL_COMPARISON.md](MODEL_COMPARISON.md). The launcher runs in the foreground; the current trial was detached with `nohup` and its PID recorded separately. Never use a broad process-name kill to manage the two llama.cpp services.

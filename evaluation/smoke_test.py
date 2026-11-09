"""Manual model + tool + LangGraph smoke test. Saves actual metrics on the server."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1")
MODEL = os.getenv("MODEL_NAME", "qwen2.5-7b-instruct")
client = OpenAI(base_url=BASE_URL, api_key=os.getenv("OPENAI_API_KEY", "local"), timeout=180)

MOCK_TOOLS = [
    {"type": "function", "function": {"name": "get_current_date",
     "description": "Return the fixed test date.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_mock_database",
     "description": "Search the fixed test database.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}},
]


def gpu_memory_mb() -> int | None:
    try:
        raw = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip().splitlines()[0]
        return int(raw)
    except Exception:
        return None


def chat(messages, **kwargs):
    started = time.perf_counter()
    response = client.chat.completions.create(model=MODEL, messages=messages, **kwargs)
    return response, time.perf_counter() - started


def main() -> int:
    report = {"model": MODEL, "base_url": BASE_URL, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "gpu_memory_before_mb": gpu_memory_mb(), "checks": {}}

    response, elapsed = chat([{"role": "user", "content": "Reply with one short English sentence confirming the local model is responding."}], max_tokens=96)
    report["checks"]["plain_api"] = {"ok": bool(response.choices[0].message.content), "seconds": elapsed,
                                      "answer": response.choices[0].message.content,
                                      "completion_tokens": response.usage.completion_tokens if response.usage else None}

    response, elapsed = chat([
        {"role": "system", "content": "Use the available tools for the requested lookup. Do not answer from memory."},
        {"role": "user", "content": "Search the mock database for the exact topic 'alpha cohort' and report the returned value."},
    ], tools=MOCK_TOOLS, tool_choice="auto", max_tokens=160)
    assistant = response.choices[0].message
    calls = assistant.tool_calls or []
    parsed_calls = []
    arguments_valid = True
    for call in calls:
        try:
            args = json.loads(call.function.arguments or "{}")
            arguments_valid = arguments_valid and isinstance(args, dict)
        except (TypeError, json.JSONDecodeError):
            args = {}
            arguments_valid = False
        parsed_calls.append((call, args))
    tool_ok = bool(calls) and arguments_valid and all(
        call.function.name in {"get_current_date", "search_mock_database"} for call, _ in parsed_calls)
    report["checks"]["tool_call"] = {"ok": tool_ok, "seconds": elapsed,
                                     "arguments_valid_json_objects": arguments_valid,
                                     "calls": [{"name": c.function.name, "arguments": c.function.arguments} for c, _ in parsed_calls],
                                     "raw_content": assistant.content}
    messages = [
        {"role": "system", "content": "Use tools and observations to answer accurately."},
        {"role": "user", "content": "Search the mock database for the exact topic 'alpha cohort' and report the returned value."},
        assistant.model_dump(exclude_none=True),
    ]
    for call, args in parsed_calls:
        if call.function.name == "search_mock_database":
            observation = {"query": args.get("query"), "result": "alpha cohort: 7 missing rows"}
        else:
            observation = {"date": "2026-11-06"}
        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(observation)})
    final, elapsed_final = chat(messages, tools=MOCK_TOOLS, tool_choice="none", max_tokens=128)
    final_text = final.choices[0].message.content or ""
    report["checks"]["mock_agent_loop"] = {"ok": bool(calls) and "7" in final_text,
                                            "seconds_including_final": elapsed + elapsed_final,
                                            "observation": "alpha cohort: 7 missing rows", "answer": final_text}

    from src.agent import run_agent
    from src.data_manager import load_csv
    frame = load_csv(PROJECT_ROOT / "examples" / "sample_data.csv")
    started = time.perf_counter()
    agent_answer, tool_log = run_agent(
        "Which columns have missing values, and what potential outlier did you find in monthly_spend?",
        frame,
    )
    agent_seconds = time.perf_counter() - started
    report["checks"]["langgraph_agent_loop"] = {
        "ok": bool(tool_log) and any(item["status"] == "ok" for item in tool_log),
        "seconds": agent_seconds, "tool_calls": [{"tool": item["tool"], "status": item["status"]} for item in tool_log],
        "answer": agent_answer,
    }

    sequential = []
    for index in range(10):
        try:
            res, seconds = chat([{"role": "user", "content": f"For a simple API stability check, say 'task {index + 1} received' in one sentence."}], max_tokens=64)
            sequential.append({"ok": bool(res.choices[0].message.content), "seconds": seconds,
                               "completion_tokens": res.usage.completion_tokens if res.usage else None})
        except Exception as exc:
            sequential.append({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    report["checks"]["sequential_10"] = {
        "successes": sum(item["ok"] for item in sequential), "total": 10, "requests": sequential,
        "average_seconds": sum(item.get("seconds", 0) for item in sequential) / 10,
    }
    report["gpu_memory_after_mb"] = gpu_memory_mb()
    report["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    output = Path(os.getenv("DATAAUDIT_RESULTS", str(PROJECT_ROOT / "results" / "smoke_test.json")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved actual results to {output}")
    required = ("plain_api", "tool_call", "mock_agent_loop", "langgraph_agent_loop")
    return 0 if all(report["checks"][key]["ok"] for key in required) and report["checks"]["sequential_10"]["successes"] == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())


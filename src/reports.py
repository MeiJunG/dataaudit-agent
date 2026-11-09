"""Store complete report artifacts independently of shortened execution previews."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any


def save_report_from_trace(trace: list[dict[str, Any]], directory: Path) -> Path | None:
    report = next((entry.get("report_markdown") for entry in reversed(trace)
                   if entry.get("tool") == "generate_quality_report" and entry.get("status") == "ok"), None)
    if not report:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("quality-report-*.md"):
        try:
            if time.time() - old.stat().st_mtime > 86400:
                old.unlink(missing_ok=True)
        except FileNotFoundError:
            pass  # Another request may already have cleaned this artifact.
    path = directory / f"quality-report-{uuid.uuid4().hex}.md"
    with path.open("x", encoding="utf-8") as output:
        output.write(str(report))
    return path

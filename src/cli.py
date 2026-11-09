"""CSV reports without a GPU, or agent questions through the configured endpoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV, TSV or Excel file to analyze")
    parser.add_argument('--sheet',help='Excel worksheet name (default: first worksheet)')
    parser.add_argument('--header-row',type=int,default=1,help='One-based header row, 1–100 (default: 1)')
    parser.add_argument("--question", help="Ask the agent a question (requires a running model API)")
    parser.add_argument("--report", type=Path, help="Write a deterministic Markdown report (no model required)")
    args = parser.parse_args(argv)
    if not args.question and args.report is None:
        parser.error("provide --question or --report")
    load_dotenv()
    from .data_manager import load_table
    from .tools import build_tools

    try:
        frame = load_table(args.csv,sheet=args.sheet,header_row=args.header_row)
        if args.report:
            report = next(tool for tool in build_tools(frame) if tool.name == "generate_quality_report").invoke({})
            args.report.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents accidentally overwriting an existing document.
            with args.report.open("x", encoding="utf-8") as target:
                target.write(str(report))
            print(f"Report: {args.report}")
        if args.question:
            from .agent import run_routed_agent as run_agent
            answer, trace = run_agent(args.question, frame)
            print(answer)
            print(f"\nTools used: {', '.join(entry['tool'] for entry in trace) or 'none'}", file=sys.stderr)
    except Exception as exc:
        print(f"Could not complete request ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

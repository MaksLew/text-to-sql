#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

COLORS = {
    "GOLD SQL": "33",
    "REWARDS": "32",
    "METRICS": "36",
    "SYSTEM": "35",
    "USER": "34",
    "ASSISTANT": "32",
    "TOOL": "33",
}
USE_COLOR = "NO_COLOR" not in os.environ and (
    sys.stdout.isatty() or "FORCE_COLOR" in os.environ
)


def color(label: str) -> str:
    return f"\033[1;{COLORS.get(label, '37')}m{label}\033[0m" if USE_COLOR else label


def show(trace: dict) -> None:
    if gold_sql := trace.get("task", {}).get("data", {}).get("gold_sql"):
        print(f"\n{color('GOLD SQL')}\n{gold_sql}")

    for heading, values in (
        ("REWARDS", trace.get("rewards", {})),
        ("METRICS", trace.get("metrics", {})),
    ):
        if values:
            print(f"\n{color(heading)}")
            for name, value in values.items():
                score = value.get("score") if isinstance(value, dict) else value
                print(f"{name}: {score}")

    for node in trace.get("nodes", []):
        message = node.get("message", {})
        role = message.get("role", "unknown").upper()

        for call in message.get("tool_calls", []):
            arguments = call.get("arguments", "{}")
            try:
                arguments = json.dumps(json.loads(arguments), indent=2)
            except (json.JSONDecodeError, TypeError):
                pass
            print(
                f"\n{color('ASSISTANT')} → {call.get('name', 'tool')}\n{arguments}"
            )

        if content := message.get("content"):
            name = f" {message['name']}" if message.get("name") else ""
            if not isinstance(content, str):
                content = json.dumps(content, indent=2)
            print(f"\n{color(role)}{name}\n{content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the readable parts of a Verifiers trace")
    parser.add_argument("traces", type=Path, help="path to traces.jsonl")
    parser.add_argument("index", type=int, nargs="?", default=0, help="zero-based trace index")
    args = parser.parse_args()

    with args.traces.open() as traces:
        for index, line in enumerate(line for line in traces if line.strip()):
            if index == args.index:
                payload = json.loads(line)
                for trace in payload.get("traces", [payload]):
                    show(trace)
                return
    parser.error(f"trace index {args.index} not found")


if __name__ == "__main__":
    main()

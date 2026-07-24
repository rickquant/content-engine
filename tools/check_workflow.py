#!/usr/bin/env python3
"""Pre-publish check for exported n8n workflows.

An n8n export is a JSON file that is easy to publish without reading. It should
not carry credentials — n8n stores those encrypted and exports only a reference —
but it does carry whatever you typed into node parameters: chat ids, phone
numbers, internal URLs, and the occasional API key pasted where it did not belong.

This script is the check I run before pushing a workflow to a public repo:

    python3 tools/check_workflow.py workflow/content-engine.workflow.json

It exits non-zero if anything looks unsafe or structurally broken, so it can sit
in a pre-commit hook or CI step.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Patterns worth failing a publish over. Each is (label, regex).
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI API key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Google API key", re.compile(r"AIza[A-Za-z0-9_\-]{30,}")),
    ("Telegram bot token", re.compile(r"\b\d{8,}:[A-Za-z0-9_\-]{30,}\b")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# Node parameters that identify a person rather than configure a step.
IDENTIFIER_FIELDS = ("chatId", "phoneNumber", "toEmail", "recipient")

PLACEHOLDER = re.compile(r"^(YOUR_|<|\{\{|\$\{|CHANGE_?ME|TODO)", re.IGNORECASE)


def find_secrets(raw: str) -> list[str]:
    """Any credential-shaped string anywhere in the file."""
    return [
        f"{label} found: {match[:12]}…"
        for label, pattern in SECRET_PATTERNS
        for match in pattern.findall(raw)
    ]


def find_identifiers(nodes: list[dict]) -> list[str]:
    """Personal identifiers left in place of a placeholder."""
    problems = []
    for node in nodes:
        params = node.get("parameters", {})
        for field in IDENTIFIER_FIELDS:
            value = params.get(field)
            if isinstance(value, str) and value and not PLACEHOLDER.match(value):
                problems.append(
                    f"node {node.get('name', '?')!r} still has a real {field}: {value}"
                )
    return problems


def find_inline_credentials(nodes: list[dict]) -> list[str]:
    """Credential references should carry a name, never the secret itself."""
    problems = []
    for node in nodes:
        for kind, ref in (node.get("credentials") or {}).items():
            if isinstance(ref, dict) and set(ref) - {"id", "name"}:
                extra = sorted(set(ref) - {"id", "name"})
                problems.append(
                    f"node {node.get('name', '?')!r} credential {kind!r} carries "
                    f"unexpected fields: {extra}"
                )
    return problems


def find_broken_graph(workflow: dict) -> list[str]:
    """Connections pointing at nodes that do not exist, and unreachable nodes."""
    names = {n.get("name") for n in workflow.get("nodes", [])}
    problems = []
    reached = set()

    for source, outputs in (workflow.get("connections") or {}).items():
        if source not in names:
            problems.append(f"connection from unknown node {source!r}")
        for groups in outputs.values():
            for group in groups:
                for link in group:
                    target = link.get("node")
                    reached.add(target)
                    if target not in names:
                        problems.append(
                            f"node {source!r} connects to unknown node {target!r}"
                        )

    sources = set(workflow.get("connections") or {})
    for node in workflow.get("nodes", []):
        name = node.get("name")
        is_trigger = "trigger" in node.get("type", "").lower()
        if not is_trigger and name not in reached and name not in sources:
            problems.append(f"node {name!r} is not connected to anything")

    return problems


def check(path: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"✗ {path}: invalid JSON — {exc}")
        return 1

    if isinstance(workflow, list):  # `n8n export:workflow --all` yields a list
        workflow = workflow[0] if workflow else {}

    nodes = workflow.get("nodes", [])
    problems = (
        find_secrets(raw)
        + find_identifiers(nodes)
        + find_inline_credentials(nodes)
        + find_broken_graph(workflow)
    )

    if problems:
        print(f"✗ {path.name}: {len(problems)} problem(s) — do not publish\n")
        for problem in problems:
            print(f"  · {problem}")
        return 1

    print(f"✓ {path.name}: {len(nodes)} nodes, no secrets, graph is consistent")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workflow", nargs="+", type=Path, help="exported n8n JSON file(s)")
    args = parser.parse_args()

    missing = [p for p in args.workflow if not p.is_file()]
    for path in missing:
        print(f"✗ {path}: file not found")

    return max([1 if missing else 0] + [check(p) for p in args.workflow if p.is_file()])


if __name__ == "__main__":
    sys.exit(main())

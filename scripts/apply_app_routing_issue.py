#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from apply_routing_issue import append_unique, extract_section
from build_app_rule_sources import EntryError, normalize_process
from build_custom_rule_sources import strip_comment


PROXY_FILE = Path("rules/apps_proxy.txt")
LOCAL_FILE = Path("rules/apps_local.txt")


def clean_entry(raw: str) -> str | None:
    """Валидируем запись как process-правило, но храним в apps_*.txt
    исходную (голую) форму — разворачивает её build_app_rule_sources.py."""
    value = strip_comment(raw)

    if not value:
        return None

    # Бросит EntryError на мусорной записи (запятая, URL, кривые символы).
    if normalize_process(value) is None:
        return None

    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--issue-number", required=True)
    args = parser.parse_args()

    event = json.loads(Path(args.issue_body).read_text(encoding="utf-8"))
    body = event["issue"]["body"]

    target = extract_section(body, "Target").strip().upper()
    entries_raw = extract_section(body, "Applications")

    if target not in {"PROXY", "DIRECT"}:
        raise ValueError(f"Unknown target: {target}")

    entries: list[str] = []

    for line in entries_raw.splitlines():
        line = line.strip()

        if not line:
            continue

        # GitHub issue forms сохраняют строки textarea как есть;
        # снимаем простые буллет-префиксы на всякий случай.
        line = re.sub(r"^[-*]\s+", "", line)

        entry = clean_entry(line)
        if entry:
            entries.append(entry)

    entries = sorted(set(entries))

    if not entries:
        raise ValueError("No valid entries found")

    if target == "PROXY":
        append_unique(PROXY_FILE, entries, args.issue_number)
    else:
        append_unique(LOCAL_FILE, entries, args.issue_number)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EntryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

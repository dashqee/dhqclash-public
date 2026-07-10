#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_custom_rule_sources import normalize_domain, normalize_ip, normalize_keyword, strip_comment


PROXY_FILE = Path("rules/custom_proxy.txt")
LOCAL_FILE = Path("rules/custom_local.txt")


def extract_section(body: str, title: str) -> str:
    pattern = re.compile(
        rf"### {re.escape(title)}\s*\n\n(?P<value>.*?)(?=\n### |\Z)",
        re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        raise ValueError(f"Cannot find section: {title}")

    return match.group("value").strip()


def normalize_entry(raw: str) -> str | None:
    value = strip_comment(raw)

    if not value:
        return None

    ip_value = normalize_ip(value)
    if ip_value:
        return ip_value

    domain_value = normalize_domain(value)
    if domain_value:
        return domain_value

    # Голое имя без точек ("ozon") — маска на любые поддомены и TLD,
    # в rules-файле хранится как есть, разворачивается при сборке.
    keyword_value = normalize_keyword(value)
    if keyword_value:
        return keyword_value

    raise ValueError(f"Cannot parse entry: {raw}")


def append_unique(path: Path, entries: list[str], issue_number: str) -> None:
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = {
        line.strip()
        for line in existing_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    new_entries = [entry for entry in entries if entry not in existing]

    if not new_entries:
        print(f"No new entries for {path}")
        return

    with path.open("a", encoding="utf-8") as f:
        if existing_text and not existing_text.endswith("\n"):
            f.write("\n")

        f.write(f"\n# From issue #{issue_number}\n")
        for entry in new_entries:
            f.write(f"{entry}\n")

    print(f"Added {len(new_entries)} entries to {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--issue-number", required=True)
    args = parser.parse_args()

    event = json.loads(Path(args.issue_body).read_text(encoding="utf-8"))
    body = event["issue"]["body"]

    target = extract_section(body, "Target").strip().upper()
    entries_raw = extract_section(body, "Domains or IP/CIDR")

    if target not in {"PROXY", "DIRECT"}:
        raise ValueError(f"Unknown target: {target}")

    entries: list[str] = []

    for line in entries_raw.splitlines():
        line = line.strip()

        if not line:
            continue

        # GitHub issue forms can preserve textarea lines as plain text.
        # Remove simple bullet prefixes just in case.
        line = re.sub(r"^[-*]\s+", "", line)

        entry = normalize_entry(line)
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
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
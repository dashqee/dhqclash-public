#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import ipaddress
import re
from pathlib import Path


DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(\*\.)?(\+\.)?([a-zA-Z0-9_-]+\.)+[a-zA-Z0-9_-]+\.?$"
)

# Голое имя без точек ("ozon", "yandex") — маска: любые поддомены, любой TLD.
KEYWORD_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def strip_comment(line: str) -> str:
    line = line.strip()

    if not line:
        return ""

    if line.startswith("#"):
        return ""

    if " #" in line:
        line = line.split(" #", 1)[0].strip()

    return line


def normalize_ip(value: str) -> str | None:
    try:
        if "/" in value:
            return str(ipaddress.ip_network(value, strict=False))

        ip = ipaddress.ip_address(value)

        if ip.version == 4:
            return f"{ip}/32"

        return f"{ip}/128"
    except ValueError:
        return None


def normalize_keyword(value: str) -> str | None:
    value = value.strip().lower()

    if value.startswith("keyword:"):
        value = value[len("keyword:"):].strip()

    if KEYWORD_RE.match(value):
        return value

    return None


def keyword_to_domains(keyword: str) -> list[str]:
    # Маска в domain-trie синтаксисе mihomo: "*" — ровно одна метка,
    # "+." — любые поддомены. Двух паттернов хватает на обычные (ozon.ru)
    # и двухуровневые (ozon.com.tr) TLD; myozon.ru не матчится.
    return [f"+.{keyword}.*", f"+.{keyword}.*.*"]


def normalize_domain(value: str) -> str | None:
    value = value.strip().lower()

    if value.startswith("http://") or value.startswith("https://"):
        raise ValueError(f"URL is not allowed, use domain only: {value}")

    for prefix in (
        "domain:",
        "suffix:",
        "domain-suffix,",
        "domain,",
        "host-suffix,",
        "host,",
    ):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()

    if value.startswith("*."):
        value = "+." + value[2:]

    if value.startswith("."):
        value = "+." + value[1:]

    value = value.rstrip("/")

    if not DOMAIN_RE.match(value):
        return None

    if value.startswith("+."):
        return value.rstrip(".")

    return "+." + value.rstrip(".")


def parse_file(input_path: Path) -> tuple[list[str], list[str]]:
    domains: list[str] = []
    ipcidrs: list[str] = []
    errors: list[str] = []

    for line_no, raw_line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        value = strip_comment(raw_line)

        if not value:
            continue

        ip_value = normalize_ip(value)
        if ip_value:
            ipcidrs.append(ip_value)
            continue

        try:
            domain_value = normalize_domain(value)
        except ValueError as e:
            errors.append(f"{input_path}:{line_no}: {e}")
            continue

        if domain_value:
            domains.append(domain_value)
            continue

        keyword_value = normalize_keyword(value)
        if keyword_value:
            domains.extend(keyword_to_domains(keyword_value))
            continue

        errors.append(f"{input_path}:{line_no}: cannot parse: {value}")

    if errors:
        print("Errors:")
        for err in errors:
            print(f" - {err}")
        raise SystemExit(1)

    return sorted(set(domains)), sorted(set(ipcidrs))


def write_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # mihomo convert-ruleset падает с panic: empty rule,
    # если входной файл пустой.
    #
    # Поэтому для пустых списков добавляем безопасный placeholder:
    # - .invalid зарезервирован для несуществующих доменов
    # - 192.0.2.0/24 зарезервирован для документации / тестов
    if not values:
        if path.name.endswith("-domains.txt"):
            values = ["+.placeholder.invalid"]
        elif path.name.endswith("-ipcidr.txt"):
            values = ["192.0.2.255/32"]

    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def build_one(name: str, source: Path, out_dir: Path) -> None:
    domains, ipcidrs = parse_file(source)

    domain_out = out_dir / f"{name}-domains.txt"
    ipcidr_out = out_dir / f"{name}-ipcidr.txt"

    write_list(domain_out, domains)
    write_list(ipcidr_out, ipcidrs)

    print(f"{name}: domains={len(domains)} -> {domain_out}")
    print(f"{name}: ipcidr={len(ipcidrs)} -> {ipcidr_out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-input", default="rules/custom_proxy.txt")
    parser.add_argument("--local-input", default="rules/custom_local.txt")
    parser.add_argument("--out-dir", default="build")
    args = parser.parse_args()

    build_one("custom-proxy", Path(args.proxy_input), Path(args.out_dir))
    build_one("custom-local", Path(args.local_input), Path(args.out_dir))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

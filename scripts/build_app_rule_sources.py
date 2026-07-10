#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from pathlib import Path

from build_custom_rule_sources import strip_comment


# Имена процессов / пакетов / путей: буквы, цифры и обычные разделители.
# Пробелы разрешены (у macOS-приложений бывают пробелы в имени).
NAME_RE = re.compile(r"^[A-Za-z0-9 ._/\\-]+$")


class EntryError(ValueError):
    pass


def normalize_process(raw: str) -> str | None:
    """Голую запись из apps_*.txt превращаем в classical-правило mihomo.

    steam.exe              -> PROCESS-NAME,steam.exe
    org.telegram.messenger -> PROCESS-NAME,org.telegram.messenger
    path:/opt/foo/foo      -> PROCESS-PATH,/opt/foo/foo
    regex:^chrom(e|ium)    -> PROCESS-NAME-REGEX,^chrom(e|ium)
    """
    value = strip_comment(raw)

    if not value:
        return None

    if "://" in value:
        raise EntryError(f"URL is not allowed, use a process name: {value}")

    # Запятая в записи означала бы, что пользователь пытается подсунуть
    # policy/target прямо в classical-пейлоад — запрещаем.
    if "," in value:
        raise EntryError(f"comma is not allowed in entry: {value}")

    lowered = value.lower()

    if lowered.startswith("path:"):
        target = value[len("path:"):].strip()
        rule_type = "PROCESS-PATH"
    elif lowered.startswith("regex:"):
        target = value[len("regex:"):].strip()
        rule_type = "PROCESS-NAME-REGEX"
    else:
        target = value
        rule_type = "PROCESS-NAME"

    if not target:
        raise EntryError(f"empty process value: {value}")

    # Regex может содержать спецсимволы (^ ( ) | и т.п.), поэтому для него
    # проверяем только отсутствие запятой (уже сделано выше). Для имён и путей
    # держим строгий набор символов.
    if rule_type != "PROCESS-NAME-REGEX" and not NAME_RE.match(target):
        raise EntryError(f"unsupported characters in entry: {value}")

    return f"{rule_type},{target}"


def parse_file(input_path: Path) -> list[str]:
    rules: list[str] = []
    errors: list[str] = []

    for line_no, raw_line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rule = normalize_process(raw_line)
        except EntryError as e:
            errors.append(f"{input_path}:{line_no}: {e}")
            continue

        if rule:
            rules.append(rule)

    if errors:
        print("Errors:")
        for err in errors:
            print(f" - {err}")
        raise SystemExit(1)

    return sorted(set(rules))


def write_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # mihomo не грузит пустой rule-provider — для пустого списка кладём
    # безопасный placeholder, который заведомо ни с чем не совпадёт.
    if not values:
        values = ["PROCESS-NAME,__dhqclash_placeholder__"]

    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def build_one(name: str, source: Path, out_dir: Path) -> None:
    rules = parse_file(source)

    out_path = out_dir / f"{name}.list"
    write_list(out_path, rules)

    print(f"{name}: rules={len(rules)} -> {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-input", default="rules/apps_proxy.txt")
    parser.add_argument("--local-input", default="rules/apps_local.txt")
    parser.add_argument("--out-dir", default="build")
    args = parser.parse_args()

    build_one("custom-apps-proxy", Path(args.proxy_input), Path(args.out_dir))
    build_one("custom-apps-local", Path(args.local_input), Path(args.out_dir))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

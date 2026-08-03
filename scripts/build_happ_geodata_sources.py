#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Create plain Xray geosite/geoip inputs for the Happ routing profile."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from build_custom_rule_sources import parse_file


KEYWORD_ONE_TLD_RE = re.compile(r'^\+\.([a-z0-9-]+)\.\*$')
KEYWORD_TWO_TLD_RE = re.compile(r'^\+\.([a-z0-9-]+)\.\*\.\*$')


def mihomo_domain_to_v2fly(value: str) -> str:
    """Translate normalized Mihomo domain-trie input to DLC source syntax."""
    two_tld = KEYWORD_TWO_TLD_RE.match(value)
    if two_tld:
        keyword = re.escape(two_tld.group(1))
        return rf'regexp:^(?:.+\.)?{keyword}\.[^.]+\.[^.]+$'
    one_tld = KEYWORD_ONE_TLD_RE.match(value)
    if one_tld:
        keyword = re.escape(one_tld.group(1))
        return rf'regexp:^(?:.+\.)?{keyword}\.[^.]+$'
    if value.startswith('+.'):
        return f'domain:{value[2:]}'
    return f'domain:{value}'


def write_section(path: Path, header: str, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# {header}', *values]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_ip_section(path: Path, values: list[str], placeholder: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(values or [placeholder]) + '\n', encoding='utf-8')


def build(proxy_input: Path, local_input: Path, out_dir: Path) -> None:
    proxy_domains, proxy_ips = parse_file(proxy_input)
    local_domains, local_ips = parse_file(local_input)

    domain_overlap = sorted(set(proxy_domains) & set(local_domains))
    ip_overlap = sorted(set(proxy_ips) & set(local_ips))
    if domain_overlap or ip_overlap:
        overlap = ', '.join([*domain_overlap, *ip_overlap])
        raise SystemExit(f'PROXY and DIRECT rules overlap: {overlap}')

    write_section(
        out_dir / 'dhq-proxy',
        'DHQ custom domains routed through the proxy',
        [mihomo_domain_to_v2fly(value) for value in proxy_domains],
    )
    write_section(
        out_dir / 'dhq-direct',
        'DHQ custom domains routed directly',
        [mihomo_domain_to_v2fly(value) for value in local_domains],
    )
    # Geomixer consumes these text files as named dhq-proxy and dhq-direct
    # sections while retaining the selected runetfreedom lists upstream.
    write_ip_section(out_dir / 'dhq-proxy-ip.txt', proxy_ips, '192.0.2.254/32')
    write_ip_section(out_dir / 'dhq-direct-ip.txt', local_ips, '192.0.2.255/32')

    print(
        f'Happ geodata sources: proxy={len(proxy_domains)} domains/{len(proxy_ips)} CIDRs, '
        f'direct={len(local_domains)} domains/{len(local_ips)} CIDRs',
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy-input', default='rules/custom_proxy.txt')
    parser.add_argument('--local-input', default='rules/custom_local.txt')
    parser.add_argument('--out-dir', default='build/happ')
    args = parser.parse_args()
    build(Path(args.proxy_input), Path(args.local_input), Path(args.out_dir))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

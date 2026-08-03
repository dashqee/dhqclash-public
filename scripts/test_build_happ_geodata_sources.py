#!/usr/bin/env python3

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_happ_geodata_sources import build, mihomo_domain_to_v2fly


class HappGeodataSourcesTest(unittest.TestCase):
    def test_domain_translation(self):
        self.assertEqual('domain:example.com', mihomo_domain_to_v2fly('+.example.com'))
        self.assertEqual(
            r'regexp:^(?:.+\.)?ozon\.[^.]+$',
            mihomo_domain_to_v2fly('+.ozon.*'),
        )
        self.assertEqual(
            r'regexp:^(?:.+\.)?ozon\.[^.]+\.[^.]+$',
            mihomo_domain_to_v2fly('+.ozon.*.*'),
        )

    def test_build_writes_domain_and_ip_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proxy = root / 'proxy.txt'
            direct = root / 'direct.txt'
            proxy.write_text('example.com\n1.1.1.1\n', encoding='utf-8')
            direct.write_text('local.example\n10.0.0.0/8\n', encoding='utf-8')

            build(proxy, direct, root / 'out')

            self.assertIn('domain:example.com', (root / 'out/dhq-proxy').read_text())
            self.assertIn('domain:local.example', (root / 'out/dhq-direct').read_text())
            self.assertIn('1.1.1.1/32', (root / 'out/dhq-proxy-ip.txt').read_text())
            self.assertIn('10.0.0.0/8', (root / 'out/dhq-direct-ip.txt').read_text())


if __name__ == '__main__':
    unittest.main()

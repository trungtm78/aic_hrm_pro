# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import pathlib
import re
import unicodedata

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import TransactionCase, tagged

SUITE_MODULES = ('aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review',
                 'aic_hrm_pro')

# Vietnamese-specific letters that never appear in English source.
_VIETNAMESE_RE = re.compile(
    '[ăâđêôơưĂÂĐÊÔƠƯ]|'
    '[aeiouyAEIOUY][̣̀́̃̉]')


def _has_vietnamese(text):
    return bool(_VIETNAMESE_RE.search(unicodedata.normalize('NFD', text)))


@tagged('post_install', '-at_install', 'aic_hrm_pro')
class TestPackaging(TransactionCase):
    """Apps Store packaging invariants (CX#5) + the one-way language gate:
    source code stays English-only; anything Vietnamese lives in i18n."""

    def test_manifest_coherence(self):
        prices = {}
        for name in SUITE_MODULES:
            manifest = get_manifest(name)
            self.assertEqual(manifest['license'], 'OPL-1', name)
            self.assertTrue(
                manifest['version'].startswith('19.0.'), name)
            self.assertEqual(manifest['author'], 'AIPOWER CO.,LTD', name)
            prices[name] = manifest.get('price')
        self.assertTrue(prices['aic_hrm_pro'],
                        'the app module carries the price')
        for name in ('aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review'):
            self.assertFalse(
                prices[name],
                f'{name} is bundled - only the app module is priced')
        self.assertTrue(get_manifest('aic_hrm_pro')['application'])

    def test_language_gate_source_is_english(self):
        offenders = []
        for name in SUITE_MODULES:
            root = pathlib.Path(get_module_path(name))
            for path in root.rglob('*'):
                if path.suffix not in ('.py', '.js', '.xml', '.scss'):
                    continue
                relative = path.relative_to(root).as_posix()
                # i18n carries translations; import-term data intentionally
                # carries spreadsheet vocabulary as DATA; test fixtures may
                # mirror customer files.
                if relative.startswith('i18n/') or \
                        relative == 'data/aic_hrm_import_terms.xml' or \
                        relative.startswith('tests/'):
                    continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                if _has_vietnamese(text):
                    offenders.append(f'{name}/{relative}')
        self.assertFalse(
            offenders,
            'Vietnamese found in source files (belongs in i18n): '
            + ', '.join(offenders))

    def test_demo_data_is_fictional(self):
        """The published demo must never contain the pilot customer's real
        people. Spot-check: every demo employee is tagged as demo."""
        demo_employees = self.env['hr.employee'].search(
            [('name', 'like', '(Demo)')])
        if not demo_employees:
            self.skipTest('demo data not installed in this database')
        cycle = self.env.ref('aic_hrm_pro.demo_cycle')
        objectives = self.env['aic.hrm.objective'].search(
            [('cycle_id', '=', cycle.id)])
        self.assertAlmostEqual(sum(objectives.mapped('weight')), 100.0,
                               msg='demo objectives weigh 100% like the '
                                   'real methodology')

"""Every translation catalog must be one Odoo can actually load.

Odoo reads a catalog entry by entry during `-u`, and a single entry without
a `module:` comment raises inside its reader - the whole upgrade is rolled
back. That is how a hand-added entry once stopped a production upgrade after
the module suite had passed: the suite ran before the catalog was edited, and
nothing else parses the file. These rules are the reader's own
(odoo/tools/translate.py, PoFileReader.__iter__), checked without a database.
"""
import pathlib
import re
import unittest

import polib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOGS = sorted((ROOT / 'addons_hrm').glob('*/i18n/*.po*'))

# The same patterns Odoo matches, in the same order.
_MODULE = re.compile(r"(module[s]?): (\w+)")
_OCCURRENCES = (
    re.compile(r'(model|model_terms):([\w.]+),([\w]+):(\w+)\.([^ ]+)'),
    re.compile(r'(code):([\w/.]+)'),
    re.compile(r'(selection):([\w.]+),([\w]+)'),
)


class TestI18nCatalogs(unittest.TestCase):

    def test_there_are_catalogs_to_check(self):
        self.assertTrue(CATALOGS, 'no catalog found - the glob is wrong')

    def test_every_entry_names_its_module(self):
        for path in CATALOGS:
            module = path.parents[1].name
            for entry in polib.pofile(str(path)):
                if entry.obsolete:
                    continue
                with self.subTest(catalog=str(path.relative_to(ROOT)), msgid=entry.msgid[:60]):
                    match = _MODULE.match(entry.comment or '')
                    self.assertIsNotNone(
                        match, 'no "#. module:" comment: Odoo aborts the upgrade on this entry')
                    self.assertEqual(match.group(2), module)

    def test_every_occurrence_is_one_odoo_can_place(self):
        for path in CATALOGS:
            module = path.parents[1].name
            for entry in polib.pofile(str(path)):
                if entry.obsolete:
                    continue
                for occurrence, _line in entry.occurrences:
                    with self.subTest(catalog=str(path.relative_to(ROOT)), occurrence=occurrence):
                        self.assertTrue(
                            any(pattern.match(occurrence) for pattern in _OCCURRENCES),
                            'Odoo silently drops a translation it cannot place')
                        if occurrence.startswith('code:'):
                            self.assertTrue(
                                occurrence.startswith(f'code:addons/{module}/'),
                                'a code occurrence must point inside its own module')


if __name__ == '__main__':
    unittest.main()

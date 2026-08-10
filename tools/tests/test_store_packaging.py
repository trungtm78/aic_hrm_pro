# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Store packaging invariants, checkable without a database.

These rules decide whether Odoo accepts the upload at all, so they must fail in
CI rather than in a reviewer's inbox. They live here, not only in the Odoo-side
``test_packaging.py``, because that one needs a running server and a database:
a rule that can only be checked by booting Odoo is a rule nobody runs before
pushing.

Run:  python -m unittest discover -s tools/tests -t .
"""
import ast
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_ADDONS = _REPO / 'addons_hrm'


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        'build_store_package', _REPO / 'tools' / 'build_store_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load_builder()


def _manifest(module):
    return ast.literal_eval(
        (_ADDONS / module / '__manifest__.py').read_text(encoding='utf-8'))


class StoreListingCase(unittest.TestCase):
    """Rules taken verbatim from the Odoo Apps vendor guidelines."""

    # "the name of the app must be explicit and should contain no more than
    # 25 characters. Avoid adjectives, or including the name of your company."
    MAX_NAME = 25

    def test_every_store_module_name_fits_the_listing_limit(self):
        offenders = []
        for module in builder.STORE_MODULES:
            name = _manifest(module)['name']
            if len(name) > self.MAX_NAME:
                offenders.append('%s: %d chars - %r' % (module, len(name), name))
        self.assertFalse(
            offenders,
            'Odoo rejects listings whose name exceeds %d characters:\n  %s'
            % (self.MAX_NAME, '\n  '.join(offenders)))

    def test_store_names_do_not_carry_the_company_name(self):
        """The guidelines ask for the product, not the publisher: the store
        already shows who published it, so the company name burns characters
        that should describe what the app does."""
        offenders = [module for module in builder.STORE_MODULES
                     if 'aiconnect' in _manifest(module)['name'].lower()
                     or 'aipower' in _manifest(module)['name'].lower()]
        self.assertFalse(offenders,
                         'company name in the listing title: %s' % offenders)

    def test_priced_apps_are_applications_with_a_full_listing(self):
        for module in builder.PRICED_APPS:
            manifest = _manifest(module)
            directory = _ADDONS / module
            self.assertTrue(manifest.get('application'),
                            '%s is priced so it must be an application' % module)
            for key in ('price', 'currency', 'support', 'images'):
                self.assertTrue(manifest.get(key),
                                '%s: priced listing has no %r' % (module, key))
            self.assertTrue((directory / 'static/description/index.html').exists(),
                            '%s: priced listing has no landing page' % module)
            for image in manifest['images']:
                self.assertTrue((directory / image).exists(),
                                '%s: images entry missing on disk: %s'
                                % (module, image))

    def test_bundled_modules_are_never_priced(self):
        """Two priced rows for one product is how a store listing ends up
        showing the same thing at two prices."""
        for module in builder.STORE_MODULES:
            if module in builder.PRICED_APPS:
                continue
            manifest = _manifest(module)
            self.assertFalse(manifest.get('price'),
                             '%s is bundled - it must not carry a price' % module)
            self.assertFalse(manifest.get('application'),
                             '%s is bundled - it must not be an application'
                             % module)

    def test_every_module_ships_its_own_license(self):
        """The builder archives one module directory per zip, so a LICENSE at
        the repository root reaches exactly none of them. An OPL-1 product
        delivered without its licence text is a legal defect, not a cosmetic
        one."""
        canonical = (_REPO / 'LICENSE').read_text(encoding='utf-8').strip()
        self.assertIn('Odoo Proprietary License', canonical)
        for module in builder.STORE_MODULES:
            path = _ADDONS / module / 'LICENSE'
            self.assertTrue(path.exists(), '%s: no LICENSE in the module' % module)
            self.assertEqual(path.read_text(encoding='utf-8').strip(), canonical,
                             '%s: LICENSE differs from the canonical text' % module)

    def test_author_string_is_byte_identical_everywhere(self):
        """The store groups a publisher's listings by this exact string, so a
        stray space splits the catalogue across two publisher pages."""
        for module in builder.STORE_MODULES:
            self.assertEqual(_manifest(module)['author'], 'AIPOWER CO., LTD',
                             '%s: author string drifted' % module)

    def test_license_key_is_opl_1(self):
        for module in builder.STORE_MODULES:
            self.assertEqual(_manifest(module)['license'], 'OPL-1', module)

    def test_all_modules_share_one_version_series(self):
        series = {module: _manifest(module)['version'].split('.')[0]
                  for module in builder.STORE_MODULES}
        self.assertEqual(len(set(series.values())), 1,
                         'mixed series across the upload set: %s' % series)


class ManifestDescriptionCase(unittest.TestCase):
    """Odoo renders `description` as reStructuredText on the module page and in
    Apps. Malformed markup does not raise - it renders wrong and logs a warning
    nobody reads, so the check belongs in CI."""

    def test_every_description_is_valid_rst(self):
        from docutils.core import publish_string

        offenders = []
        for module in sorted(p.name for p in _ADDONS.iterdir() if p.is_dir()):
            manifest_path = _ADDONS / module / '__manifest__.py'
            if not manifest_path.exists():
                continue
            description = ast.literal_eval(
                manifest_path.read_text(encoding='utf-8')).get('description', '')
            if not description.strip():
                continue
            messages = []
            publish_string(
                source=description, writer_name='html4css1',
                settings_overrides={
                    'report_level': 2, 'halt_level': 5,
                    'warning_stream': type(
                        'Sink', (object,),
                        {'write': lambda self, text: messages.append(text.strip())}
                    )()})
            noise = [m for m in messages if m]
            if noise:
                offenders.append('%s: %s' % (module, noise[0].splitlines()[0]))
        self.assertFalse(offenders,
                         'malformed reStructuredText in manifests:\n  %s'
                         % '\n  '.join(offenders))


class AccessCsvCase(unittest.TestCase):
    """Structural checks on every ir.model.access.csv in the suite.

    A malformed row does not fail loudly: Odoo reports "Missing required value
    for the field 'Model'" during install, which points at the symptom and not
    at the line. Catching the shape here turns a confusing install failure into
    a one-line CI message.
    """

    HEADER = ('id,name,model_id:id,group_id:id,'
              'perm_read,perm_write,perm_create,perm_unlink')

    def _csv_paths(self):
        return sorted(_ADDONS.glob('*/security/ir.model.access.csv'))

    def test_every_row_has_the_right_number_of_columns(self):
        offenders = []
        for path in self._csv_paths():
            for number, line in enumerate(
                    path.read_text(encoding='utf-8').splitlines(), start=1):
                if not line.strip():
                    continue
                if len(line.split(',')) != 8:
                    offenders.append('%s:%d has %d columns'
                                     % (path.relative_to(_REPO), number,
                                        len(line.split(','))))
        self.assertFalse(offenders, '\n  '.join(offenders))

    def test_the_header_is_the_expected_one(self):
        for path in self._csv_paths():
            first = path.read_text(encoding='utf-8').splitlines()[0]
            self.assertEqual(first, self.HEADER, path.relative_to(_REPO))

    def test_access_ids_are_unique_within_a_file(self):
        for path in self._csv_paths():
            ids = [line.split(',')[0]
                   for line in path.read_text(encoding='utf-8').splitlines()[1:]
                   if line.strip()]
            duplicates = {i for i in ids if ids.count(i) > 1}
            self.assertFalse(duplicates,
                             '%s: duplicate ids %s'
                             % (path.relative_to(_REPO), sorted(duplicates)))

    def test_permissions_are_zero_or_one(self):
        for path in self._csv_paths():
            for number, line in enumerate(
                    path.read_text(encoding='utf-8').splitlines()[1:], start=2):
                if not line.strip():
                    continue
                for value in line.split(',')[4:]:
                    self.assertIn(value, ('0', '1'),
                                  '%s:%d' % (path.relative_to(_REPO), number))


class BuilderContractCase(unittest.TestCase):
    """The builder is the only thing that produces the upload, so its own
    knobs are part of the packaging contract."""

    def test_builder_exposes_the_priced_set(self):
        self.assertTrue(hasattr(builder, 'PRICED_APPS'))
        self.assertTrue(set(builder.PRICED_APPS) <= set(builder.STORE_MODULES))

    def test_series_is_a_parameter_not_a_constant(self):
        """A hard-coded series makes the 18.0 release command fail every
        module, which is exactly what it used to do."""
        import inspect
        source = inspect.getsource(builder)
        self.assertNotIn("startswith('19.0.')", source,
                         'series must come from --series, not a literal')
        self.assertIn('--series', source)

    def test_check_rejects_a_bundled_module_that_carries_a_price(self):
        problems = builder.check(
            _ADDONS / 'aic_hrm_base',
            {'license': 'OPL-1', 'version': '19.0.1.0.0', 'price': 5.0},
            is_app=False, series='19.0')
        self.assertTrue(any('price' in p for p in problems), problems)

    def test_check_rejects_a_missing_license_file(self):
        problems = builder.check(
            _REPO / 'tools',                       # a directory with no LICENSE
            {'license': 'OPL-1', 'version': '19.0.1.0.0'},
            is_app=False, series='19.0')
        self.assertTrue(any('LICENSE' in p for p in problems), problems)

    def test_standalone_apps_never_reach_into_the_performance_suite(self):
        """The staffing app is sold to a delivery lead, not an HR director.
        The moment it depends on the suite it stops being buyable on its own,
        and the 25 USD listing silently requires a 130 USD prerequisite."""
        for module, allowed in builder.STANDALONE_APPS.items():
            depends = set(_manifest(module)['depends'])
            self.assertFalse(
                depends & builder.PERFORMANCE_SUITE,
                '%s depends on the performance suite: %s'
                % (module, sorted(depends & builder.PERFORMANCE_SUITE)))
            self.assertTrue(
                depends <= allowed,
                '%s gained a dependency outside its allowed set: %s'
                % (module, sorted(depends - allowed)))

    def test_connectors_auto_install_and_stay_free(self):
        for module in ('aic_hrm_match_okr', 'aic_hrm_match_timesheet'):
            manifest = _manifest(module)
            self.assertTrue(manifest['auto_install'],
                            '%s is a connector; it should install itself once '
                            'both sides are present' % module)
            self.assertFalse(manifest.get('price'), module)
            self.assertIn('aic_hrm_match', manifest['depends'], module)

    def test_modules_that_define_ui_ship_a_translation_catalogue(self):
        """Whoever defines the screens owes the translation. A bundle module
        that only carries demo data and a store listing has no UI strings, so
        demanding a catalogue from it would fail the build over nothing."""
        missing = [module for module in builder.STORE_MODULES
                   if builder.defines_ui(_ADDONS / module)
                   and not (_ADDONS / module / 'i18n' / 'vi.po').exists()]
        self.assertFalse(missing, 'UI modules without vi.po: %s' % missing)

    def test_bundle_module_is_not_asked_for_a_catalogue(self):
        """aic_hrm_pro is models-free on purpose; the rule must not fire."""
        bundle = _ADDONS / 'aic_hrm_pro'
        self.assertFalse(builder.defines_ui(bundle))
        problems = builder.check(bundle, _manifest('aic_hrm_pro'),
                                 is_app=True, series='19.0')
        self.assertFalse([p for p in problems if 'vi.po' in p], problems)

    def test_check_rejects_an_over_long_listing_name(self):
        problems = builder.check(
            _ADDONS / 'aic_hrm_base',
            {'license': 'OPL-1', 'version': '19.0.1.0.0',
             'name': 'A name that is definitely longer than twenty five'},
            is_app=False, series='19.0')
        self.assertTrue(any('name' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main()

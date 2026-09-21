# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Every browser file a module ships is in its asset bundle.

A file left out of the bundle is not a build error and not a test failure:
the browser simply cannot resolve the import, the component stops rendering,
and the screen comes up blank on the customer's instance. That is how the
leadership desk went dark after a helper was moved into a file of its own.
The manifests are read as text, so this needs no database and no Odoo.

Run:  python -m unittest discover -s tools/tests -t .
"""
import ast
import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
ADDONS = _REPO / 'addons_hrm'
WEB_FILES = ('.js', '.xml', '.scss', '.css')
# Templates loaded by a view or a report, not by the browser bundle.
NOT_BUNDLED = re.compile(r'static[\\/](lib|tests|description)[\\/]')


def manifests():
    return sorted(ADDONS.glob('*/__manifest__.py'))


def declared(manifest):
    data = ast.literal_eval(manifest.read_text(encoding='utf-8'))
    listed = set()
    for bundle in (data.get('assets') or {}).values():
        for entry in bundle:
            path = entry[0] if isinstance(entry, (list, tuple)) else entry
            listed.add(str(path).split('/', 1)[-1] if '/' in str(path) else str(path))
    return listed, data


class AssetBundleCase(unittest.TestCase):

    def test_every_browser_file_is_in_a_bundle(self):
        for manifest in manifests():
            module = manifest.parent
            listed, _data = declared(manifest)
            for path in sorted((module / 'static' / 'src').rglob('*')):
                if path.suffix not in WEB_FILES or NOT_BUNDLED.search(str(path)):
                    continue
                relative = path.relative_to(module).as_posix()
                with self.subTest(module=module.name, file=relative):
                    self.assertIn(relative, listed,
                                  f'{module.name}: {relative} không có trong assets, '
                                  f'trình duyệt sẽ không tải được')

    def test_every_bundled_file_exists(self):
        for manifest in manifests():
            module = manifest.parent
            listed, _data = declared(manifest)
            for relative in sorted(listed):
                if not relative.startswith('static/'):
                    continue
                with self.subTest(module=module.name, file=relative):
                    self.assertTrue((module / relative).exists(),
                                    f'{module.name}: assets khai báo {relative} nhưng không có tệp')

    def test_a_shared_helper_is_bundled_before_the_screens_that_import_it(self):
        """Order matters inside a bundle: the importer must come after."""
        for manifest in manifests():
            module = manifest.parent
            _listed, data = declared(manifest)
            for bundle in (data.get('assets') or {}).values():
                files = [str(entry).split('/', 1)[-1] for entry in bundle
                         if str(entry).endswith('.js')]
                for index, relative in enumerate(files):
                    source = module / relative
                    if not source.exists():
                        continue
                    for match in re.finditer(r'from\s+"\.\.?/([^"]+)"',
                                             source.read_text(encoding='utf-8')):
                        target = (source.parent / (match.group(1) + '.js')).resolve()
                        try:
                            wanted = target.relative_to(module).as_posix()
                        except ValueError:
                            continue
                        if wanted in files:
                            with self.subTest(module=module.name, file=relative):
                                self.assertLess(files.index(wanted), index,
                                                f'{relative} nạp trước {wanted} mà nó cần')


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Build the Odoo Apps Store upload for the suite.

One zip per module, because that is what the store takes. Working files
never ship: translation drafts, byte-code caches, the local documentation
folder with real customer data in it.

aic_hrm_brand is deliberately NOT built. It exists to remove the
platform vendor's own branding, which is fine for a direct on-premise
delivery under LGPL but is not something to submit to that vendor's
store. It ships with the customer hand-off instead.

Usage:  python tools/build_store_package.py [--dest dist]
"""
import argparse
import ast
import os
import pathlib
import shutil
import zipfile

STORE_MODULES = [
    'aic_hrm_base',
    'aic_okr_kpi',
    'aic_hrm_library',
    'aic_hrm_review',
    'aic_hrm_project',
    'aic_hrm_sale',
    'aic_hrm_pro',
]
WITHHELD = {'aic_hrm_brand': 'debrands the platform vendor - direct delivery only'}

EXCLUDE_DIRS = {'__pycache__', '.pytest_cache', '.ruff_cache'}
EXCLUDE_SUFFIX = ('.pyc', '.pyo', '.draft', '.orig', '.rej')


def read_manifest(module_dir):
    text = (module_dir / '__manifest__.py').read_text(encoding='utf-8')
    return ast.literal_eval(text)


def check(module_dir, manifest, is_flagship):
    """Refuse to ship a module the store would bounce."""
    problems = []
    if manifest.get('license') != 'OPL-1':
        problems.append('license is %r, expected OPL-1'
                        % manifest.get('license'))
    version = str(manifest.get('version', ''))
    if not version.startswith('19.0.'):
        problems.append('version %r is not 19.0.x' % version)
    if not (module_dir / 'static/description/icon.png').exists():
        problems.append('no static/description/icon.png')
    if is_flagship:
        for key in ('price', 'currency', 'support', 'images'):
            if not manifest.get(key):
                problems.append('flagship manifest has no %r' % key)
        if not (module_dir / 'static/description/index.html').exists():
            problems.append('no static/description/index.html')
        for image in manifest.get('images', []):
            if not (module_dir / image).exists():
                problems.append('images entry missing on disk: %s' % image)
    return problems


def add_module(zip_path, module_dir, module):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(module_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in sorted(files):
                if name.endswith(EXCLUDE_SUFFIX):
                    continue
                full = pathlib.Path(root) / name
                # The store unpacks into addons/, so the module directory
                # itself has to be the top level inside the archive.
                arc = pathlib.Path(module) / full.relative_to(module_dir)
                archive.write(full, arc.as_posix())
    return zip_path.stat().st_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dest', default='dist')
    parser.add_argument('--source', default='addons_hrm')
    args = parser.parse_args()

    source = pathlib.Path(args.source).resolve()
    dest = pathlib.Path(args.dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    failures = []
    total = 0
    for module in STORE_MODULES:
        module_dir = source / module
        manifest = read_manifest(module_dir)
        problems = check(module_dir, manifest, module == 'aic_hrm_pro')
        if problems:
            failures.append((module, problems))
            continue
        size = add_module(dest / ('%s.zip' % module), module_dir, module)
        total += size
        print('%-18s %6.1f KB  v%s' % (module, size / 1024,
                                       manifest['version']))

    for module, why in WITHHELD.items():
        print('%-18s WITHHELD  (%s)' % (module, why))

    if failures:
        print('\nNOT PACKAGED:')
        for module, problems in failures:
            for problem in problems:
                print('  %-18s %s' % (module, problem))
        raise SystemExit(1)

    print('\n%d archives, %.1f KB total -> %s'
          % (len(STORE_MODULES), total / 1024, dest))


if __name__ == '__main__':
    main()

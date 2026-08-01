# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Merge hand-maintained Vietnamese translations into the exported .pot.

The suite keeps its translation dictionary in ``i18n/vi.draft`` (plain
msgid/msgstr pairs); Odoo's PO loader additionally requires the occurrence
metadata that only ``odoo-bin i18n export`` produces. This script marries
the two: pot structure + draft translations -> ``vi.po``.

Usage: python tools/merge_vi_translations.py [--lang vi] <module_dir> [...]
"""
import argparse
from pathlib import Path

import polib


def merge(module_dir, lang):
    module = Path(module_dir)
    pot_path = next(module.glob('i18n/*.pot'))
    draft_path = module / 'i18n' / f'{lang}.draft'
    draft = polib.pofile(str(draft_path)) if draft_path.exists() else []
    translations = {entry.msgid: entry.msgstr
                    for entry in draft if entry.msgstr}
    pot = polib.pofile(str(pot_path))
    translated = 0
    for entry in pot:
        if entry.msgid in translations:
            entry.msgstr = translations[entry.msgid]
            translated += 1
    pot.metadata.update({
        'Language': lang,
        'Content-Type': 'text/plain; charset=UTF-8',
        'Plural-Forms': 'nplurals=1; plural=0;',
    })
    out_path = module / 'i18n' / f'{lang}.po'
    pot.save(str(out_path))
    print(f'{module.name} [{lang}]: {translated}/{len(pot)} entries '
          f'translated -> {out_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', default='vi')
    parser.add_argument('modules', nargs='+')
    args = parser.parse_args()
    for path in args.modules:
        merge(path, args.lang)

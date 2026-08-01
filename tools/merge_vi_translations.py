# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Merge hand-maintained Vietnamese translations into the exported .pot.

The suite keeps its translation dictionary in ``i18n/vi.draft`` (plain
msgid/msgstr pairs); Odoo's PO loader additionally requires the occurrence
metadata that only ``odoo-bin i18n export`` produces. This script marries
the two: pot structure + draft translations -> ``vi.po``.

Usage: python tools/merge_vi_translations.py <module_dir> [...]
"""
import sys
from pathlib import Path

import polib


def merge(module_dir):
    module = Path(module_dir)
    pot_path = next(module.glob('i18n/*.pot'))
    draft_path = module / 'i18n' / 'vi.draft'
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
        'Language': 'vi',
        'Content-Type': 'text/plain; charset=UTF-8',
        'Plural-Forms': 'nplurals=1; plural=0;',
    })
    out_path = module / 'i18n' / 'vi.po'
    pot.save(str(out_path))
    print(f'{module.name}: {translated}/{len(pot)} entries translated '
          f'-> {out_path}')


if __name__ == '__main__':
    for path in sys.argv[1:]:
        merge(path)

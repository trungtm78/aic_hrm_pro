# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Produce the Odoo 18 build of the suite from the 19.0 source tree.

Verified API deltas between Odoo 19 and Odoo 18 (probed against both source
trees, see docs/backport-notes.md):

1. Manifest version prefix ``19.0.x`` -> ``18.0.x``.
2. ``models.Constraint`` class attributes -> legacy ``_sql_constraints``.
3. ``res.groups.privilege`` records / ``privilege_id`` -> ``category_id``.
4. ``res.users.group_ids`` -> ``groups_id`` (test fixtures).

Everything else used by the suite (``_has_cycle``, ``<chatter/>``, ``<list>``,
``aggregator=``, ``_read_group`` tuple API, ``Many2oneReference``) exists in
both versions.

Usage: python tools/backport_18.py [--source addons_hrm] [--dest build/18.0]
"""
import argparse
import pathlib
import re
import shutil

CONSTRAINT_RE = re.compile(
    r"^(?P<indent>[ \t]*)_(?P<name>\w+) = models\.Constraint\(\n"
    r"(?P<indent2>[ \t]*)'(?P<definition>[^']*)',\n"
    r"[ \t]*'(?P<message>[^']*)',?\n"
    r"[ \t]*\)\n",
    re.MULTILINE)

PRIVILEGE_RECORD_RE = re.compile(
    r"[ \t]*<record id=\"[^\"]*\" model=\"res\.groups\.privilege\">.*?"
    r"</record>\n", re.DOTALL)

PRIVILEGE_FIELD_RE = re.compile(
    r"<field name=\"privilege_id\" ref=\"[^\"]*\"/>")

# res.groups in Odoo 18 has no `sequence` field (19 added it for the new
# privilege-based settings UI). Strip it from group records only.
GROUP_SEQUENCE_RE = re.compile(
    r"(<record id=\"group_[^\"]*\" model=\"res\.groups\">(?:(?!</record>).)*?)"
    r"[ \t]*<field name=\"sequence\">\d+</field>\n",
    re.DOTALL)


def transform_python(text):
    def to_sql_constraint(match):
        return (
            "{indent}_sql_constraints = [\n"
            "{indent}    ('{name}', '{definition}', '{message}'),\n"
            "{indent}]\n"
        ).format(
            indent=match.group('indent'),
            name=match.group('name'),
            definition=match.group('definition').replace("unique (", "unique("),
            message=match.group('message'),
        )

    text = CONSTRAINT_RE.sub(to_sql_constraint, text)
    text = text.replace("'group_ids': [(6, 0, [", "'groups_id': [(6, 0, [")
    text = text.replace(
        "'version': '19.0.", "'version': '18.0.")
    return text


def transform_xml(text):
    text = PRIVILEGE_RECORD_RE.sub("", text)
    text = PRIVILEGE_FIELD_RE.sub(
        '<field name="category_id" ref="base.module_category_human_resources"/>',
        text)
    while True:
        text, count = GROUP_SEQUENCE_RE.subn(r"\1", text)
        if not count:
            break
    # res.groups.user_ids (19) was `users` in 18.
    text = text.replace('<field name="user_ids" eval=',
                        '<field name="users" eval=')
    return text


def transform_js(text):
    # Odoo 18 keeps tour utils under tour_service/.
    return text.replace('from "@web_tour/tour_utils"',
                        'from "@web_tour/tour_service/tour_utils"')


def backport(source, dest):
    source = pathlib.Path(source)
    dest = pathlib.Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    changed = 0
    for path in dest.rglob('*'):
        if path.suffix == '.py':
            original = path.read_text(encoding='utf-8')
            updated = transform_python(original)
        elif path.suffix == '.xml':
            original = path.read_text(encoding='utf-8')
            updated = transform_xml(original)
        elif path.suffix == '.js':
            original = path.read_text(encoding='utf-8')
            updated = transform_js(original)
        else:
            continue
        if updated != original:
            path.write_text(updated, encoding='utf-8', newline='\n')
            changed += 1
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='addons_hrm')
    parser.add_argument('--dest', default='build/18.0')
    args = parser.parse_args()
    count = backport(args.source, args.dest)
    print(f'Backported to {args.dest}: {count} files transformed')

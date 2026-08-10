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

Two-stage by design. ``backport()`` rewrites what it recognises; ``verify()``
then proves nothing Odoo-19-only survived. The second stage exists because the
first one used to fail silently: a declaration shape the rewriter did not match
was copied through untouched, the run still reported success, and an 18.0 zip
could reach a customer carrying API that only exists in 19. A transform without
a verifier is a transform you cannot trust.

Usage: python tools/backport_18.py [--source addons_hrm] [--dest build/18.0]
"""
import argparse
import ast
import pathlib
import re
import shutil

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

# Directories whose contents quote source code as DATA rather than execute it.
# A translation catalogue legitimately contains the English string it
# translates, and the store landing page legitimately names fields in prose;
# scanning either would make the gate report findings that are not defects.
VERIFY_SKIP_PARTS = ('i18n', 'description')

# marker -> file suffixes it applies to. Each entry is a literal substring
# whose presence in the 18.0 build means the transform did not run or did not
# recognise the shape it was given.
RESIDUAL_MARKERS = (
    ('models.Constraint', ('.py',)),
    ("'version': '19.0.", ('.py',)),
    ("'group_ids':", ('.py',)),
    ('res.groups.privilege', ('.xml',)),
    ('privilege_id', ('.xml',)),
    ('@web_tour/tour_utils', ('.js',)),
)


def _render_sql_constraints(indent, entries):
    """Emit the Odoo 18 legacy declaration for one class.

    Entries are rendered with ``repr`` rather than interpolated between
    hand-written quotes: a constraint message containing an apostrophe is
    ordinary English ("the team's name"), and quoting it by hand is how you
    produce a build that fails to import.
    """
    lines = ['%s_sql_constraints = [' % indent]
    for name, definition, message in entries:
        lines.append('%s    (%r, %r, %r),' % (indent, name, definition, message))
    lines.append('%s]' % indent)
    return '\n'.join(lines) + '\n'


def _constraint_entries(class_node):
    """Return (entries, spans) for one class body.

    ``spans`` are 1-based inclusive line ranges to delete. Odoo 18 takes a
    single ``_sql_constraints`` list, so several ``models.Constraint``
    attributes on one class have to merge into one assignment - emitting one
    per attribute would leave only the last one in effect.
    """
    entries, spans, indent = [], [], None
    for node in class_node.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.startswith('_'):
            continue
        call = node.value
        if not (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == 'Constraint'
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'models'):
            continue
        if len(call.args) != 2 or call.keywords:
            # Leave it alone on purpose: verify() will refuse the build rather
            # than let a shape we do not understand through as a silent no-op.
            continue
        try:
            definition = ast.literal_eval(call.args[0])
            message = ast.literal_eval(call.args[1])
        except (ValueError, SyntaxError):
            continue
        if not isinstance(definition, str) or not isinstance(message, str):
            continue
        entries.append((target.id.lstrip('_'),
                        definition.replace('unique (', 'unique('),
                        message))
        spans.append((node.lineno, node.end_lineno))
        if indent is None:
            indent = ' ' * node.col_offset
    return entries, spans, indent or '    '


def _transform_constraints(text):
    """Rewrite every ``models.Constraint`` attribute into ``_sql_constraints``.

    Parsed with ``ast`` rather than matched with a regular expression: the
    regex this replaces recognised exactly one layout (four lines, single
    quotes) and silently ignored a wrapped message or a double-quoted string,
    which are both ordinary Python.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines(keepends=True)
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        entries, spans, indent = _constraint_entries(node)
        if not entries:
            continue
        edits.append((spans, _render_sql_constraints(indent, entries)))
    if not edits:
        return text
    # Apply bottom-up so earlier line numbers stay valid while we splice.
    flat = []
    for spans, rendered in edits:
        first = spans[0]
        flat.append((first[0], first[1], rendered))
        for span in spans[1:]:
            flat.append((span[0], span[1], ''))
    for start, end, rendered in sorted(flat, reverse=True):
        lines[start - 1:end] = [rendered] if rendered else []
    return ''.join(lines)


def transform_python(text):
    text = _transform_constraints(text)
    text = text.replace("'group_ids': [(6, 0, [", "'groups_id': [(6, 0, [")
    text = text.replace("'version': '19.0.", "'version': '18.0.")
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


def verify(dest):
    """Return every Odoo-19-only construct still present under ``dest``.

    Each finding is ``(relative_posix_path, line_number, marker)``. An empty
    list is the only result that means the build is safe to package.
    """
    dest = pathlib.Path(dest)
    findings = []
    for path in sorted(dest.rglob('*')):
        if not path.is_file():
            continue
        markers = [m for m, suffixes in RESIDUAL_MARKERS
                   if path.suffix in suffixes]
        if not markers:
            continue
        relative = path.relative_to(dest)
        if VERIFY_SKIP_PARTS and set(relative.parts) & set(VERIFY_SKIP_PARTS):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if not any(marker in text for marker in markers):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for marker in markers:
                if marker in line:
                    findings.append((relative.as_posix(), number, marker))
    return findings


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
    problems = verify(args.dest)
    if problems:
        print('\nODOO 19 API SURVIVED THE TRANSFORM - build not shippable:')
        for relative, line, marker in problems:
            print('  %s:%s  %s' % (relative, line, marker))
        raise SystemExit(1)
    print('Verified: no Odoo-19-only API remains.')

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""View syntax that Odoo 19 removed, and that fails loudly but late.

Three attributes were dropped between Odoo 16 and 19. None of them degrades
gracefully: the view loader rejects the whole file, which aborts the module
install, which takes down every test in the suite with an error that names the
XML line and says nothing about what to write instead.

That makes them expensive to find and trivial to check, which is what this file
is for. It needs no database and runs in under a second, so a mistake surfaces
at the point it was made rather than after a fifteen-minute install.

The rules, and what replaced them:

* ``<tree>`` became ``<list>`` in Odoo 17, along with ``view_mode="tree"``.
* ``attrs="{'invisible': [...]}"`` became ``invisible="<python expression>"``.
* ``states="draft,ranked"`` became ``invisible="state not in (...)"``.
"""
import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDONS = REPO_ROOT / 'addons_hrm'

# Matched on the opening tag only. "tree" appears legitimately inside strings
# and comments - a help text mentioning a tree of tags is not a defect.
TREE_TAG = re.compile(r'<tree[\s>/]')
VIEW_MODE_TREE = re.compile(r'view_mode="[^"]*\btree\b')
# The same setting is written as element text on an ir.actions.act_window
# record, which the attribute pattern above cannot see. Missing that form is how
# a menu action kept asking for a view type Odoo 19 no longer has.
VIEW_MODE_TREE_ELEMENT = re.compile(
    r'<field\s+name="view_mode"\s*>[^<]*\btree\b')
MODE_TREE = re.compile(r'\bmode="tree"')
# Renamed in Odoo 19, and unlike the rest this one does not fail at install:
# the view loads, and the browser throws "Missing 'card' template." when
# somebody opens the kanban. Only a tour or a human would ever have found it.
KANBAN_BOX = re.compile(r't-name="kanban-box"')
ATTRS = re.compile(r'\battrs\s*=')
STATES = re.compile(r'\bstates\s*=')

FORBIDDEN = (
    (TREE_TAG, '<tree> was renamed to <list> in Odoo 17'),
    (VIEW_MODE_TREE, 'view_mode="tree" became view_mode="list" in Odoo 17'),
    (VIEW_MODE_TREE_ELEMENT,
     '<field name="view_mode">tree</field> became list in Odoo 17'),
    (MODE_TREE, 'mode="tree" on a One2many became mode="list" in Odoo 17'),
    (KANBAN_BOX,
     't-name="kanban-box" became t-name="card" in Odoo 19'),
    (ATTRS, 'attrs= was removed in Odoo 17; use invisible/readonly/required '
            'with a Python expression'),
    (STATES, 'states= was removed in Odoo 17; use invisible="state not in (...)"'),
)


def _xml_files():
    return sorted(ADDONS.rglob('*.xml'))


class ViewSyntaxCase(unittest.TestCase):

    def test_no_view_uses_syntax_odoo_19_rejects(self):
        """One offending attribute anywhere aborts the install of the module
        that owns it, so this is checked across the whole suite rather than
        per module."""
        offences = []
        for path in _xml_files():
            text = path.read_text(encoding='utf-8')
            for number, line in enumerate(text.splitlines(), start=1):
                for pattern, explanation in FORBIDDEN:
                    if pattern.search(line):
                        offences.append('%s:%d - %s'
                                        % (path.relative_to(REPO_ROOT),
                                           number, explanation))
        self.assertFalse(offences, 'Odoo 19 will refuse these views:\n  '
                         + '\n  '.join(offences))

    def test_the_check_would_notice(self):
        """A guard nobody has seen fail is a guard nobody knows works. Each
        pattern is exercised against the shape it exists to catch."""
        samples = [
            ('<tree editable="bottom">', TREE_TAG),
            ('<field name="x" view_mode="tree,form"/>', VIEW_MODE_TREE),
            ('<field name="ids" mode="tree">', MODE_TREE),
            ('<t t-name="kanban-box">', KANBAN_BOX),
            ('<field name="view_mode">kanban,tree,form</field>',
             VIEW_MODE_TREE_ELEMENT),
            ("""<page attrs="{'invisible': [('state', '=', 'draft')]}">""", ATTRS),
            ('<button name="go" states="draft"/>', STATES),
        ]
        for line, pattern in samples:
            self.assertTrue(pattern.search(line), line)

    def test_the_check_leaves_valid_views_alone(self):
        """The patterns must not fire on the replacements, or fixing a file
        would be impossible."""
        allowed = [
            '<list editable="bottom">',
            '<field name="ids" mode="list">',
            '<page invisible="state == \'draft\'">',
            '<button name="go" invisible="state not in (\'draft\',)"/>',
            '<field name="parent_id" help="Position in the tag tree"/>',
            '<field name="view_mode">kanban,list,form</field>',
            '<t t-name="card">',
        ]
        for line in allowed:
            for pattern, explanation in FORBIDDEN:
                self.assertFalse(pattern.search(line),
                                 '%s wrongly flagged by: %s'
                                 % (line, explanation))


if __name__ == '__main__':
    unittest.main()

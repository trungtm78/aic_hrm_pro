# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Guard the 19 -> 18 transform against the failure mode that has no symptom.

``backport()`` used to report only how many files it rewrote. A construct it
did not recognise was copied through untouched and the build still looked
successful, so an Odoo-19-only API could reach a customer inside an 18.0 zip.
Every test here exists to make that silence impossible: either the transform
handles the shape, or ``verify()`` refuses to let the tree ship.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

_TOOLS = pathlib.Path(__file__).resolve().parents[1]


def _load_backport():
    """Import tools/backport_18.py by path: tools/ is a script folder, not a
    package on sys.path, and adding it to sys.path would leak into other tests.
    """
    spec = importlib.util.spec_from_file_location(
        'backport_18', _TOOLS / 'backport_18.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backport_18 = _load_backport()


# Three shapes of the same declaration. Only the first one was ever handled.
CONSTRAINT_PLAIN = """\
class Demo(models.Model):
    _name = 'demo.plain'

    _code_uniq = models.Constraint(
        'unique (code)',
        'Codes must be unique.',
    )
"""

CONSTRAINT_DOUBLE_QUOTED = """\
class Demo(models.Model):
    _name = 'demo.double'

    _code_uniq = models.Constraint(
        "unique (code, company_id)",
        "Codes must be unique per company.",
    )
"""

# A message long enough that a developer wraps it - implicit concatenation is
# the idiomatic way to do that in Python and produces a single string.
CONSTRAINT_WRAPPED_MESSAGE = """\
class Demo(models.Model):
    _name = 'demo.wrapped'

    _window_uniq = models.Constraint(
        'unique (employee_id, date_start, date_end)',
        'This person already has a booking that covers exactly this '
        'window; merge the two instead of creating a duplicate.',
    )
"""


class BackportTransformCase(unittest.TestCase):
    """The transform must recognise every shape a developer may legitimately
    write, not only the one that happened to exist when it was written."""

    def _transform(self, source):
        return backport_18.transform_python(source)

    def test_plain_constraint_becomes_sql_constraints(self):
        result = self._transform(CONSTRAINT_PLAIN)
        self.assertNotIn('models.Constraint', result)
        self.assertIn('_sql_constraints = [', result)
        self.assertIn("('code_uniq', 'unique(code)', 'Codes must be unique.')",
                      result)

    def test_double_quoted_constraint_is_transformed(self):
        result = self._transform(CONSTRAINT_DOUBLE_QUOTED)
        self.assertNotIn('models.Constraint', result)
        self.assertIn('unique(code, company_id)', result)
        self.assertIn('Codes must be unique per company.', result)

    def test_wrapped_message_constraint_is_transformed(self):
        """Implicit string concatenation must survive as one joined message,
        not as two arguments and not as an unrecognised block."""
        result = self._transform(CONSTRAINT_WRAPPED_MESSAGE)
        self.assertNotIn('models.Constraint', result)
        self.assertIn('_sql_constraints = [', result)
        self.assertIn('merge the two instead of creating a duplicate.', result)

    def test_indentation_is_preserved(self):
        result = self._transform(CONSTRAINT_PLAIN)
        for line in result.splitlines():
            if '_sql_constraints' in line:
                self.assertTrue(line.startswith('    '),
                                'constraint must stay inside the class body')
                break
        else:
            self.fail('no _sql_constraints line produced')

    def test_version_and_group_ids_are_rewritten(self):
        source = ("'version': '19.0.1.0.0',\n"
                  "'group_ids': [(6, 0, [ref('base.group_user')])],\n")
        result = self._transform(source)
        self.assertIn("'version': '18.0.1.0.0'", result)
        self.assertIn("'groups_id': [(6, 0,", result)
        self.assertNotIn("'group_ids': [(6, 0,", result)


class BackportVerifyCase(unittest.TestCase):
    """``verify()`` is the net under the transform. A shape the transform
    misses must stop the build here rather than ship."""

    def setUp(self):
        self.tree = pathlib.Path(tempfile.mkdtemp(prefix='aic-backport-'))
        self.addCleanup(shutil.rmtree, self.tree, True)

    def _write(self, relative, text):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_clean_tree_reports_nothing(self):
        self._write('models/demo.py',
                    backport_18.transform_python(CONSTRAINT_PLAIN))
        self._write('__manifest__.py', "{'version': '18.0.1.0.0'}\n")
        self.assertEqual(backport_18.verify(self.tree), [])

    def test_residual_constraint_is_reported(self):
        self._write('models/demo.py', CONSTRAINT_PLAIN)
        findings = backport_18.verify(self.tree)
        self.assertTrue(findings)
        self.assertIn('models.Constraint', findings[0][2])

    def test_residual_privilege_record_is_reported(self):
        self._write('security/groups.xml',
                    '<odoo>\n'
                    '  <record id="p" model="res.groups.privilege"/>\n'
                    '</odoo>\n')
        markers = [f[2] for f in backport_18.verify(self.tree)]
        self.assertIn('res.groups.privilege', markers)

    def test_residual_privilege_field_is_reported(self):
        self._write('security/groups.xml',
                    '<field name="privilege_id" ref="x"/>\n')
        markers = [f[2] for f in backport_18.verify(self.tree)]
        self.assertIn('privilege_id', markers)

    def test_residual_tour_import_is_reported(self):
        self._write('static/src/tours/t.js',
                    'import { stepUtils } from "@web_tour/tour_utils";\n')
        markers = [f[2] for f in backport_18.verify(self.tree)]
        self.assertIn('@web_tour/tour_utils', markers)

    def test_residual_19_version_is_reported(self):
        self._write('__manifest__.py', "{'version': '19.0.1.0.0'}\n")
        markers = [f[2] for f in backport_18.verify(self.tree)]
        self.assertIn("'version': '19.0.", markers)

    def test_residual_group_ids_fixture_is_reported(self):
        self._write('tests/test_x.py',
                    "cls.env['res.users'].create({'group_ids': [(6, 0, [])]})\n")
        markers = [f[2] for f in backport_18.verify(self.tree)]
        self.assertIn("'group_ids':", markers)

    def test_findings_carry_file_and_line(self):
        self._write('models/demo.py', '\n\n' + CONSTRAINT_PLAIN)
        relative, line, _marker = backport_18.verify(self.tree)[0]
        self.assertEqual(relative, 'models/demo.py')
        self.assertEqual(line, 6, 'line number must point at the offending row')

    def test_i18n_and_docs_are_not_scanned(self):
        """Translation catalogues quote source strings verbatim; treating that
        quotation as a live API reference would make the gate cry wolf."""
        self._write('i18n/vi.po', 'msgid "models.Constraint"\n')
        self._write('static/description/index.html',
                    '<p>privilege_id</p>\n')
        self.assertEqual(backport_18.verify(self.tree), [])

    def test_backport_then_verify_is_clean_for_the_real_suite(self):
        """End to end on the shipped modules: transform, then prove nothing
        Odoo-19-only survived."""
        source = pathlib.Path(__file__).resolve().parents[2] / 'addons_hrm'
        if not source.is_dir():
            self.skipTest('addons_hrm not present')
        dest = self.tree / 'build18'
        backport_18.backport(source, dest)
        self.assertEqual(
            backport_18.verify(dest), [],
            'the 18.0 build still contains Odoo-19-only API')


if __name__ == '__main__':
    unittest.main()

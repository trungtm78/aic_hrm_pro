# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The one place that knows how this Odoo stores skill validity.

Odoo 19 models certification periods natively: hr.individual.skill.mixin has
valid_from/valid_to, hr.skill.type has is_certification, and the overlap rule
deliberately lets one skill carry several periods. Odoo 18 has none of that and
enforces unique(employee_id, skill_id), so a second period is not merely absent,
it is forbidden.

Everything the engine asks about validity goes through this service, and these
tests run on both series unchanged: they assert the *behaviour*, never which
branch produced it. That is the whole point - a test that says "on 18 do this"
would pass while the engine read the wrong column.
"""
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class SkillCompatDetectionCase(MatchCase):

    def test_capability_is_detected_from_fields_not_from_a_version_number(self):
        """Probing the series would be wrong twice over: a patch release can
        move a field, and a customer may run a fork. Ask the model what it has.
        """
        compat = self.env['aic.hrm.match.skill.compat']
        self.assertEqual(
            compat.has_core_validity(),
            'valid_to' in self.env['hr.employee.skill']._fields)
        self.assertEqual(
            compat.has_core_certification(),
            'is_certification' in self.env['hr.skill.type']._fields)

    def test_the_two_capabilities_are_reported_independently(self):
        """They arrived together in 19 but they are separate questions, and a
        fork could ship one without the other."""
        compat = self.env['aic.hrm.match.skill.compat']
        self.assertIsInstance(compat.has_core_validity(), bool)
        self.assertIsInstance(compat.has_core_certification(), bool)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class SkillValidityCase(MatchCase):
    """Reading validity, whichever side of the split we are on."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compat = cls.env['aic.hrm.match.skill.compat']
        cls.skill_type, cls.skill, cls.level = cls._make_skill_set(
            'Cloud', 'AWS', certification=False)
        cls.cert_type, cls.cert_skill, cls.cert_level = cls._make_skill_set(
            'Certifications', 'AWS Solutions Architect', certification=True)
        cls.employee = cls._make_employee('Skill Owner')

    def test_an_ordinary_skill_never_expires(self):
        """Only certifications expire.

        This is not a technicality. On Odoo 19 ``valid_from`` defaults to the
        day the line was created, so date-checking plain skills would fail a
        developer who has written Python for a decade purely because HR entered
        the record this morning and the project started last month.
        """
        line = self._make_employee_skill(self.employee, self.skill)
        self.assertTrue(self.compat.certification_covers_window(
            line, '2026-01-01', '2026-12-31'))

    def test_a_certification_without_an_end_date_is_open_ended(self):
        line = self._make_employee_skill(
            self.employee, self.cert_skill, valid_from='2020-01-01')
        self.assertTrue(self.compat.certification_covers_window(
            line, '2026-01-01', '2026-12-31'))

    def test_a_certification_is_date_checked(self):
        """The other half of the same rule: what does not expire is exempt,
        what does expire is checked."""
        line = self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-01-01', valid_to='2026-06-30')
        self.assertFalse(self.compat.certification_covers_window(
            line, '2026-01-01', '2026-12-31'))

    def test_a_line_must_cover_the_whole_window_not_just_its_end(self):
        """The gate this replaces only compared valid_to against the end date,
        which let a certificate starting mid-project count for the whole of it.
        """
        line = self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-06-01', valid_to='2026-12-31')
        self.assertFalse(self.compat.covers_window(
            line, '2026-01-01', '2026-12-31'))
        self.assertTrue(self.compat.covers_window(
            line, '2026-07-01', '2026-08-31'))

    def test_a_line_that_expires_inside_the_window_does_not_cover_it(self):
        line = self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-01-01', valid_to='2026-06-30')
        self.assertFalse(self.compat.covers_window(
            line, '2026-01-01', '2026-12-31'))

    def test_a_line_covering_exactly_the_window_counts(self):
        """Boundary dates are inclusive: a certificate valid to the last day of
        the work is valid for that work."""
        line = self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-01-01', valid_to='2026-12-31')
        self.assertTrue(self.compat.covers_window(
            line, '2026-01-01', '2026-12-31'))

    def test_get_validity_returns_one_map_for_a_batch(self):
        """The engine asks once for every line it is about to score; asking per
        line is the per-record query loop the performance budget forbids."""
        line = self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-01-01', valid_to='2026-12-31')
        validity = self.compat.get_validity(line)
        self.assertIn(line.id, validity)
        valid_from, valid_to = validity[line.id]
        self.assertEqual(str(valid_from), '2026-01-01')
        self.assertEqual(str(valid_to), '2026-12-31')

    def test_get_validity_of_nothing_is_an_empty_map(self):
        self.assertEqual(
            self.compat.get_validity(self.env['hr.employee.skill']), {})

    def test_the_service_tolerates_empty_recordsets_throughout(self):
        """An employee with no skills at all is an ordinary candidate - they
        simply score nothing on skill fit. Every entry point has to answer
        rather than raise, or the ranking dies on the first such person."""
        no_lines = self.env['hr.employee.skill']
        no_types = self.env['hr.skill.type']
        self.assertIsNone(self.compat.set_validity(no_lines, '2026-01-01'))
        self.assertFalse(self.compat.is_certification(no_types))
        self.assertIsNone(self.compat.set_certification(no_types, True))

    def test_writing_validity_goes_to_whichever_column_this_series_has(self):
        """The caller states the fact; the service decides where it lives."""
        line = self._make_employee_skill(self.employee, self.cert_skill)
        self.compat.set_validity(line, '2026-03-01', '2027-03-01')
        valid_from, valid_to = self.compat.get_validity(line)[line.id]
        self.assertEqual(str(valid_from), '2026-03-01')
        self.assertEqual(str(valid_to), '2027-03-01')


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CertificationTypeCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compat = cls.env['aic.hrm.match.skill.compat']
        cls.plain_type, cls.plain_skill, _level = cls._make_skill_set(
            'Languages', 'English', certification=False)
        cls.cert_type, cls.cert_skill, _cert_level = cls._make_skill_set(
            'Vendor Certifications', 'PMP', certification=True)

    def test_certification_types_are_reported(self):
        type_ids = self.compat.get_certification_type_ids()
        self.assertIn(self.cert_type.id, type_ids)
        self.assertNotIn(self.plain_type.id, type_ids)

    def test_is_certification_answers_per_skill_type(self):
        self.assertTrue(self.compat.is_certification(self.cert_type))
        self.assertFalse(self.compat.is_certification(self.plain_type))

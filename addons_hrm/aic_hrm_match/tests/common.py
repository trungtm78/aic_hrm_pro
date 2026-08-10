# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Shared fixtures for the staffing tests.

Factories are classmethods returning records so a test can say what it is about
in one line and leave everything it does not care about to the default. A test
whose first ten lines build a skill taxonomy is a test whose subject is hidden.
"""
from odoo.tests import TransactionCase


class MatchCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env['res.company'].create({
            'name': 'Second Company (test)',
        })
        cls.TagCategory = cls.env['aic.hrm.match.tag.category']
        cls.Tag = cls.env['aic.hrm.match.tag']
        cls.Seniority = cls.env['aic.hrm.match.seniority']

        cls.category_tech = cls._make_tag_category(
            code='technology', name='Technology')
        cls.category_industry = cls._make_tag_category(
            code='industry', name='Industry', similarity_weight=1.5)

    # -- factories ----------------------------------------------------------

    @classmethod
    def _make_tag_category(cls, **kwargs):
        values = {
            'code': 'domain',
            'name': 'Domain',
            'is_hierarchical': True,
        }
        values.update(kwargs)
        return cls.TagCategory.create(values)

    @classmethod
    def _make_tag(cls, **kwargs):
        values = {
            'name': 'Backend',
            'code': 'backend',
            'category_id': cls.category_tech.id,
        }
        values.update(kwargs)
        return cls.Tag.create(values)

    @classmethod
    def _make_seniority(cls, **kwargs):
        values = {'code': 'mid', 'name': 'Mid', 'rank': 20}
        values.update(kwargs)
        return cls.Seniority.create(values)

    @classmethod
    def _make_employee(cls, name, **kwargs):
        values = {'name': name, 'company_id': cls.company.id}
        values.update(kwargs)
        return cls.env['hr.employee'].create(values)

    DEFAULT_LEVELS = (('Beginner', 25), ('Confirmed', 60), ('Expert', 100))

    @classmethod
    def _make_skill_set(cls, type_name, skill_name, certification=False,
                        levels=None):
        """Create a skill type with its skills and levels in one call.

        The certification flag is set through the compat service rather than
        written directly: the column only exists on Odoo 19, and a fixture that
        assumes it turns every test in this file into a 19-only test.
        """
        skill_type = cls.env['hr.skill.type'].create({'name': type_name})
        cls.env['aic.hrm.match.skill.compat'].set_certification(
            skill_type, certification)
        skill = cls.env['hr.skill'].create({
            'name': skill_name, 'skill_type_id': skill_type.id})
        level_records = cls.env['hr.skill.level']
        for index, (level_name, progress) in enumerate(levels
                                                       or cls.DEFAULT_LEVELS):
            level_records |= cls.env['hr.skill.level'].create({
                'name': level_name,
                'level_progress': progress,
                'skill_type_id': skill_type.id,
                'default_level': index == 0,
            })
        return skill_type, skill, level_records[-1]

    @classmethod
    def _make_employee_skill(cls, employee, skill, level=None,
                             valid_from=None, valid_to=None):
        level = level or skill.skill_type_id.skill_level_ids[-1]
        line = cls.env['hr.employee.skill'].create({
            'employee_id': employee.id,
            'skill_id': skill.id,
            'skill_type_id': skill.skill_type_id.id,
            'skill_level_id': level.id,
        })
        if valid_from or valid_to:
            cls.env['aic.hrm.match.skill.compat'].set_validity(
                line, valid_from, valid_to)
        return line

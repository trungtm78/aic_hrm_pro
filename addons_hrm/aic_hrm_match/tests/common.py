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
    def _make_active_policy(cls, code='shared_test_policy'):
        """An active policy scoring on availability, created once.

        Reused rather than recreated because only one policy per code may be
        active at a time, and because a test that searches for whatever policy
        happens to be active depends on which test ran before it - green in a
        full run, red on its own.
        """
        existing = cls.env['aic.hrm.match.policy'].search(
            [('code', '=', code), ('state', '=', 'active')], limit=1)
        if existing:
            return existing
        criterion = cls.env['aic.hrm.match.criterion'].search(
            [('code', '=', 'availability')], limit=1)
        if not criterion:
            criterion = cls.env['aic.hrm.match.criterion'].create({
                'code': 'availability', 'name': 'Availability',
                'category': 'availability', 'normalization': 'ratio'})
        policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Shared test policy', 'code': code, 'is_default': True,
            'persist_mode': 'full'})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': criterion.id,
            'weight': 1.0})
        policy.action_activate()
        return policy

    @classmethod
    def _run_match(cls, request=None, employee_count=3):
        """A completed ranking, with everything it needs behind it.

        Tests about what happens *after* a ranking - decisions, waivers,
        erasure - should not have to build a policy, a request and a pool
        before they can say anything. They get a run and the people in it.
        """
        cls._make_active_policy()
        if not getattr(cls, 'employees', None):
            cls.employees = cls.env['hr.employee'].browse()
            for index in range(employee_count):
                cls.employees |= cls._make_employee(
                    'Pooled Candidate %d' % (index + 1))
        if request is None:
            request = cls.env['aic.hrm.match.request'].create({
                'name': 'Shared test request',
                'date_start': '2026-09-14 00:00:00',
                'date_end': '2026-09-18 23:59:59'})
            cls.env['aic.hrm.match.request.slot'].create({
                'request_id': request.id, 'name': 'Developer',
                'required_hours': 8.0})
        return cls.env['aic.hrm.match.engine'].run_match(request)

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
    def _make_user(cls, name, groups, company=None, companies=None):
        """A user with exactly the staffing groups named, and nothing else.

        Built from ``base.group_user`` upwards rather than by copying an
        existing user: inheriting somebody else's groups is how a security test
        ends up proving that an administrator can read something.
        """
        company = company or cls.company
        group_records = cls.env['res.groups'].browse([
            cls.env.ref('aic_hrm_match.%s' % group).id for group in groups])
        group_records |= cls.env.ref('base.group_user')
        return cls.env['res.users'].create({
            'name': name,
            'login': 'staffing_%s' % name.lower().replace(' ', '_'),
            'company_id': company.id,
            'company_ids': [(6, 0, (companies or company).ids)],
            'group_ids': [(6, 0, group_records.ids)],
        })

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

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

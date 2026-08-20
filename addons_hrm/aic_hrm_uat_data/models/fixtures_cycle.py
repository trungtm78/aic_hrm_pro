# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Cycle fixtures - one per state of the cycle state map, plus the two
calendars that break arithmetic.

`cycle.open.D-45` is the one everything else hangs off: a year that started
45 days ago, so elapsed time is a real fraction and "behind plan" means
something. A cycle that starts today makes every pace calculation trivially
zero and hides the bug that matters.
"""
from odoo import api, models


class AicHrmUatFixtureCycle(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog.update({
            'cycle.draft.D0': {
                'doc': "A cycle nobody has opened yet. Planning is allowed, "
                       "execution is not.",
                'entity': 'cycle', 'state': 'draft', 'lifecycle': 'D0',
                'shape': 'empty', 'depends': [],
                'setup': '_setup_cycle_draft',
                'outputs': ['cycle_id', 'code'],
            },
            'cycle.open.D-45': {
                'doc': "The working cycle: a year that began 45 days ago, so "
                       "elapsed-time expectations are a real fraction.",
                'entity': 'cycle', 'state': 'open', 'lifecycle': 'D-45',
                'shape': 'normal', 'depends': [],
                'setup': '_setup_cycle_open',
                'outputs': ['cycle_id', 'quarter_cycle_id', 'code',
                            'date_start', 'date_end'],
            },
            'cycle.review.D0': {
                'doc': "A cycle in its review window - scoring is settled, "
                       "the conversation is not.",
                'entity': 'cycle', 'state': 'review', 'lifecycle': 'D0',
                'shape': 'empty', 'depends': [],
                'setup': '_setup_cycle_review',
                'outputs': ['cycle_id', 'code'],
            },
            'cycle.closed.D0': {
                'doc': "A closed cycle: still editable by an administrator, "
                       "unlike a locked one.",
                'entity': 'cycle', 'state': 'closed', 'lifecycle': 'D0',
                'shape': 'empty', 'depends': [],
                'setup': '_setup_cycle_closed',
                'outputs': ['cycle_id', 'code'],
            },
            'cycle.locked.D0': {
                'doc': "A locked cycle holding one objective and one key "
                       "result, both created before the lock. Every write "
                       "against them must now be refused.",
                'entity': 'cycle', 'state': 'locked', 'lifecycle': 'D0',
                'shape': 'normal', 'depends': ['org.base.D0'],
                'setup': '_setup_cycle_locked',
                'outputs': ['cycle_id', 'objective_id', 'kr_id', 'code'],
            },
            'cycle.open.oneday': {
                'doc': "A cycle that starts and ends on the same day. The "
                       "elapsed-time denominator is zero here, and the "
                       "progress report has to survive it.",
                'entity': 'cycle', 'state': 'open', 'lifecycle': 'oneday',
                'shape': 'empty', 'depends': [],
                'setup': '_setup_cycle_oneday',
                'outputs': ['cycle_id', 'code'],
            },
        })
        return catalog

    def _new_cycle(self, name, code, cycle_type, start, end, **extra):
        values = {
            'name': name, 'code': code, 'cycle_type': cycle_type,
            'date_start': start, 'date_end': end,
        }
        values.update(extra)
        cycle = self.env['aic.hrm.cycle'].create(values)
        return self._track([cycle])[0]

    def _advance(self, cycle, *states):
        for state in states:
            cycle.write({'state': state})
        return cycle

    def _setup_cycle_draft(self, ctx):
        cycle = self._new_cycle(
            'UAT Draft Year', 'UAT-DRAFT', 'year',
            self._day(0), self._day(364))
        return {'cycle_id': cycle.id, 'code': cycle.code}

    def _setup_cycle_open(self, ctx):
        start, end = self._day(-45), self._day(319)
        cycle = self._new_cycle('UAT Working Year', 'UAT-OPEN', 'year',
                                start, end)
        # A quarter inside the year: cross-cycle alignment (quarter -> year)
        # is only legal through this parent relation.
        quarter = self._new_cycle(
            'UAT Working Quarter', 'UAT-OPEN-Q', 'quarter',
            self._day(-45), self._day(45), parent_id=cycle.id)
        self._advance(cycle, 'open')
        self._advance(quarter, 'open')
        return {
            'cycle_id': cycle.id, 'quarter_cycle_id': quarter.id,
            'code': cycle.code,
            'date_start': str(start), 'date_end': str(end),
        }

    def _setup_cycle_review(self, ctx):
        cycle = self._new_cycle('UAT Review Year', 'UAT-REVIEW', 'year',
                                self._day(-330), self._day(35))
        self._advance(cycle, 'open', 'review')
        return {'cycle_id': cycle.id, 'code': cycle.code}

    def _setup_cycle_closed(self, ctx):
        cycle = self._new_cycle('UAT Closed Year', 'UAT-CLOSED', 'year',
                                self._day(-400), self._day(-35))
        self._advance(cycle, 'open', 'review', 'closed')
        return {'cycle_id': cycle.id, 'code': cycle.code}

    def _setup_cycle_locked(self, ctx):
        org = ctx['org.base.D0']
        cycle = self._new_cycle('UAT Locked Year', 'UAT-LOCKED', 'year',
                                self._day(-760), self._day(-395))
        objective = self.env['aic.hrm.objective'].create({
            'name': 'UAT Locked Objective', 'cycle_id': cycle.id,
            'level': 'department',
            'department_id': org['dept_product_id'],
            'employee_id': org['manager_employee_id'],
            'weight': 100.0,
        })
        self._track([objective])
        kr = self.env['aic.hrm.key.result'].create({
            'name': 'UAT Locked Key Result', 'objective_id': objective.id,
            'metric_type': 'number', 'direction': 'higher',
            'baseline': 0.0, 'target': 100.0, 'current': 60.0,
            'weight': 1.0,
        })
        self._track([kr])
        self._advance(cycle, 'open', 'review', 'closed', 'locked')
        return {'cycle_id': cycle.id, 'objective_id': objective.id,
                'kr_id': kr.id, 'code': cycle.code}

    def _setup_cycle_oneday(self, ctx):
        today = self._day(0)
        cycle = self._new_cycle('UAT Single Day', 'UAT-ONEDAY', 'custom',
                                today, today)
        self._advance(cycle, 'open')
        return {'cycle_id': cycle.id, 'code': cycle.code}

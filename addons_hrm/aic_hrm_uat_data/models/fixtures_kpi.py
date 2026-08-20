# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""KPI target, period result and scorecard fixtures.

The scorecard weights are the sharp edge. A personal scorecard may only be
submitted when its line weights sum to exactly 100, and the spreadsheet import
used to produce scorecards summing to 7-20% while reporting success - every
one of them stuck in draft, invisibly. So the dataset carries all three cases
side by side: a balanced one, an 80% one that must refuse to submit, and one
made of thirds - 33.33 + 33.33 + 33.34 - the commonest real shape, which has
to be accepted.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, models


class AicHrmUatFixtureKpi(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog.update({
            'kpi_target.confirmed.D-90.normal': {
                'doc': "A higher-is-better KPI with three confirmed monthly "
                       "results covering the last quarter.",
                'entity': 'kpi_target', 'state': 'confirmed',
                'lifecycle': 'D-90', 'shape': 'normal',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_kpi_confirmed',
                'outputs': ['kpi_id', 'target_id', 'period_result_ids',
                            'confirmed_count'],
            },
            'kpi_target.draft_results.D-30.normal': {
                'doc': "Monthly results left in draft. Scoring and the "
                       "progress report must both ignore them; a number "
                       "nobody confirmed is not a result.",
                'entity': 'kpi_target', 'state': 'draft_results',
                'lifecycle': 'D-30', 'shape': 'normal',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_kpi_draft_results',
                'outputs': ['kpi_id', 'target_id', 'period_result_ids'],
            },
            'kpi_target.lower_better.D-60.normal': {
                'doc': "Lower-is-better (defect escape rate) with a positive "
                       "target, beating plan - achievement above 1.0 before "
                       "the cap applies.",
                'entity': 'kpi_target', 'state': 'lower_better',
                'lifecycle': 'D-60', 'shape': 'normal',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_kpi_lower_better',
                'outputs': ['kpi_id', 'target_id', 'period_result_ids'],
            },
            'kpi_target.cap12.D-60.normal': {
                'doc': "A cycle whose score cap is 1.2, with a KPI that "
                       "overachieves past it - the clamp has to bite at 1.2, "
                       "not at 1.0 and not at the raw ratio.",
                'entity': 'kpi_target', 'state': 'cap12',
                'lifecycle': 'D-60', 'shape': 'normal',
                'depends': ['org.base.D0'],
                'setup': '_setup_kpi_cap12',
                'outputs': ['cycle_id', 'kpi_id', 'target_id'],
            },
            'assignment.balanced.D0': {
                'doc': "A personal scorecard weighing exactly 100 and "
                       "approved - the happy path.",
                'entity': 'assignment', 'state': 'balanced',
                'lifecycle': 'D0', 'shape': 'normal',
                'depends': ['kpi_target.confirmed.D-90.normal',
                            'kpi_target.lower_better.D-60.normal'],
                'setup': '_setup_assignment_balanced',
                'outputs': ['assignment_id', 'total_weight'],
            },
            'assignment.underweight.D0': {
                'doc': "A scorecard weighing 80. It must be impossible to "
                       "submit, and it must say so out loud rather than "
                       "sitting in draft looking finished.",
                'entity': 'assignment', 'state': 'underweight', 'lifecycle': 'D0',
                'shape': 'sparse',
                'depends': ['kpi_target.confirmed.D-90.normal'],
                'setup': '_setup_assignment_underweight',
                'outputs': ['assignment_id', 'total_weight'],
            },
            'assignment.rounding.D0': {
                'doc': "Thirds: 33.33 + 33.33 + 33.34 - three near-equal "
                       "responsibilities, the commonest way a real "
                       "scorecard is built. It sums to 100 and must be "
                       "accepted; the weight gate compares at a declared "
                       "precision rather than trusting float equality.",
                'entity': 'assignment', 'state': 'rounding', 'lifecycle': 'D0',
                'shape': 'normal',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_assignment_rounding',
                'outputs': ['assignment_id', 'total_weight'],
            },
        })
        return catalog

    # ------------------------------------------------------------------
    def _new_kpi(self, values):
        kpi = self.env['aic.hrm.kpi'].create(values)
        return self._track([kpi])[0]

    def _new_target(self, values):
        target = self.env['aic.hrm.kpi.target'].create(values)
        return self._track([target])[0]

    def _monthly_results(self, target, actuals, state='confirmed'):
        """One result per whole month, most recent last.

        `actuals` is read backwards from the current month, so the fixture
        keeps its shape whatever today happens to be.
        """
        Result = self.env['aic.hrm.kpi.period.result']
        created = Result.browse()
        for index, actual in enumerate(reversed(actuals)):
            first = self._month(-index).replace(day=1)
            last = first + relativedelta(months=1, days=-1)
            created |= Result.create({
                'kpi_target_id': target.id,
                'date_from': first, 'date_to': last,
                'actual': actual, 'state': state, 'source': 'manual',
            })
        self._track(created)
        return created

    def _setup_kpi_confirmed(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        kpi = self._new_kpi({
            'name': 'UAT Qualified leads', 'code': 'UAT-LEADS',
            'direction': 'higher', 'aggregation': 'sum', 'unit': 'leads',
            'frequency': 'monthly', 'default_target': 300.0,
        })
        target = self._new_target({
            'kpi_id': kpi.id, 'cycle_id': cycle['cycle_id'],
            'employee_id': org['member_employee_id'],
            'baseline_value': 100.0, 'target_value': 300.0, 'weight': 60.0,
        })
        results = self._monthly_results(target, [70.0, 95.0, 110.0])
        target.action_confirm()
        return {'kpi_id': kpi.id, 'target_id': target.id,
                'period_result_ids': results.ids,
                'confirmed_count': len(results)}

    def _setup_kpi_draft_results(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        kpi = self._new_kpi({
            'name': 'UAT Unreviewed survey score', 'code': 'UAT-SURVEY',
            'direction': 'higher', 'aggregation': 'average', 'unit': 'pts',
            'frequency': 'monthly', 'default_target': 80.0,
        })
        target = self._new_target({
            'kpi_id': kpi.id, 'cycle_id': cycle['cycle_id'],
            'employee_id': org['no_job_employee_id'],
            'baseline_value': 50.0, 'target_value': 80.0, 'weight': 10.0,
        })
        results = self._monthly_results(target, [95.0, 99.0], state='draft')
        return {'kpi_id': kpi.id, 'target_id': target.id,
                'period_result_ids': results.ids}

    def _setup_kpi_lower_better(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        kpi = self._new_kpi({
            'name': 'UAT Defect escape rate', 'code': 'UAT-ESCAPES',
            'direction': 'lower', 'aggregation': 'average', 'unit': '%',
            'frequency': 'monthly', 'default_target': 2.0,
        })
        target = self._new_target({
            'kpi_id': kpi.id, 'cycle_id': cycle['cycle_id'],
            'employee_id': org['member_employee_id'],
            'baseline_value': 5.0, 'target_value': 2.0, 'weight': 40.0,
            'direction': 'lower',
        })
        results = self._monthly_results(target, [1.8, 1.5, 1.2])
        target.action_confirm()
        return {'kpi_id': kpi.id, 'target_id': target.id,
                'period_result_ids': results.ids}

    def _setup_kpi_cap12(self, ctx):
        org = ctx['org.base.D0']
        cycle = self.env['aic.hrm.cycle'].create({
            'name': 'UAT Overachievement Year', 'code': 'UAT-CAP12',
            'cycle_type': 'year', 'date_start': self._day(-60),
            'date_end': self._day(305), 'score_cap': 1.2,
        })
        self._track([cycle])
        cycle.write({'state': 'open'})
        kpi = self._new_kpi({
            'name': 'UAT Expansion revenue', 'code': 'UAT-EXPANSION',
            'direction': 'higher', 'aggregation': 'sum', 'unit': 'kUSD',
            'frequency': 'monthly', 'default_target': 100.0,
        })
        target = self._new_target({
            'kpi_id': kpi.id, 'cycle_id': cycle.id,
            'employee_id': org['manager_employee_id'],
            'baseline_value': 0.0, 'target_value': 100.0, 'weight': 100.0,
        })
        # 150 against a target of 100 is an achievement of 1.5; the cycle cap
        # of 1.2 is what the score has to land on.
        self._monthly_results(target, [150.0])
        target.action_confirm()
        return {'cycle_id': cycle.id, 'kpi_id': kpi.id, 'target_id': target.id}

    # ------------------------------------------------------------------
    def _new_assignment(self, values):
        assignment = self.env['aic.hrm.kpi.assignment'].create(values)
        return self._track([assignment])[0]

    def _setup_assignment_balanced(self, ctx):
        org = ctx['org.base.D0']
        assignment = self._new_assignment({
            'employee_id': org['member_employee_id'],
            'cycle_id': ctx['cycle.open.D-45']['cycle_id'],
            'job_note': 'UAT UI/UX Designer',
            'line_ids': [
                (0, 0, {'kpi_target_id':
                        ctx['kpi_target.confirmed.D-90.normal']['target_id'],
                        'weight': 60.0}),
                (0, 0, {'kpi_target_id':
                        ctx['kpi_target.lower_better.D-60.normal']['target_id'],
                        'weight': 40.0}),
            ],
        })
        assignment.action_submit()
        assignment.action_approve()
        return {'assignment_id': assignment.id,
                'total_weight': assignment.total_weight}

    def _setup_assignment_underweight(self, ctx):
        org = ctx['org.base.D0']
        assignment = self._new_assignment({
            'employee_id': org['manager_employee_id'],
            'cycle_id': ctx['cycle.open.D-45']['cycle_id'],
            'job_note': 'UAT Product Manager',
            'line_ids': [
                (0, 0, {'kpi_target_id':
                        ctx['kpi_target.confirmed.D-90.normal']['target_id'],
                        'weight': 80.0}),
            ],
        })
        return {'assignment_id': assignment.id,
                'total_weight': assignment.total_weight}

    def _setup_assignment_rounding(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        # One KPI per line: a target is unique per (kpi, cycle, owner), so
        # three lines for one person need three distinct KPIs, not three
        # targets on the same one.
        targets = []
        for index in range(3):
            kpi = self._new_kpi({
                'name': 'UAT Third %s' % (index + 1),
                'code': 'UAT-THIRD-%s' % (index + 1),
                'direction': 'higher', 'aggregation': 'last', 'unit': 'pts',
                'frequency': 'monthly', 'default_target': 10.0,
            })
            weight = 33.34 if index == 2 else 33.33
            targets.append(self._new_target({
                'kpi_id': kpi.id, 'cycle_id': cycle['cycle_id'],
                'employee_id': org['no_department_employee_id'],
                'target_value': 10.0 * (index + 1),
                'weight': weight, 'unit': 'pts',
            }))
        assignment = self._new_assignment({
            'employee_id': org['no_department_employee_id'],
            'cycle_id': cycle['cycle_id'],
            'line_ids': [
                (0, 0, {'kpi_target_id': target.id, 'weight': target.weight})
                for target in targets],
        })
        assignment.action_submit()
        return {'assignment_id': assignment.id,
                'total_weight': assignment.total_weight}

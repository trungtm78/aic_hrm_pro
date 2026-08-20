# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Objective, key result and check-in fixtures.

Shapes matter here more than states. An objective with no key results scores
nothing and must not be silently counted as zero; an objective nested five
levels deep is where weighted roll-up either holds or quietly loses a branch;
a key result whose last check-in was a month ago is the whole reason the
staleness machinery exists.
"""
from odoo import api, models


class AicHrmUatFixtureOkr(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog.update({
            'objective.draft.D-30.empty': {
                'doc': "A drafted objective with no key results at all - it "
                       "has nothing to score and must not read as 0%.",
                'entity': 'objective', 'state': 'draft', 'lifecycle': 'D-30',
                'shape': 'empty',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_objective_empty',
                'outputs': ['objective_id'],
            },
            'objective.approved.D-30.normal': {
                'doc': "An approved department objective with four key "
                       "results, one per metric type: number, percentage, "
                       "milestones and done/not-done.",
                'entity': 'objective', 'state': 'approved',
                'lifecycle': 'D-30', 'shape': 'normal',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_objective_normal',
                'outputs': ['objective_id', 'kr_number_id', 'kr_percent_id',
                            'kr_milestone_id', 'kr_boolean_id',
                            'milestone_ids'],
            },
            'objective.done.D-30.full': {
                'doc': "Five levels in one chain - company, branch, "
                       "department, team, individual - so weighted roll-up "
                       "is exercised across every level the product has.",
                'entity': 'objective', 'state': 'done', 'lifecycle': 'D-30',
                'shape': 'full',
                'depends': ['org.base.D0', 'cycle.open.D-45'],
                'setup': '_setup_objective_full',
                'outputs': ['company_objective_id', 'branch_objective_id',
                            'department_objective_id', 'team_objective_id',
                            'individual_objective_id', 'team_id'],
            },
            'kr.checkins.D0.normal': {
                'doc': "One key result checked in three times - 30 days ago, "
                       "7 days ago and today - so progress over time has a "
                       "real curve to draw.",
                'entity': 'kr', 'state': 'checkins',
                'lifecycle': 'D0', 'shape': 'normal',
                'depends': ['objective.approved.D-30.normal'],
                'setup': '_setup_kr_checkins',
                'outputs': ['kr_id', 'checkin_ids', 'dates'],
            },
            'kr.stale.D-30.with_holes': {
                'doc': "A key result whose only check-in was 30 days ago: "
                       "stale under any frequency the product offers, and "
                       "the input the alert rules are supposed to catch.",
                'entity': 'kr', 'state': 'stale',
                'lifecycle': 'D-30', 'shape': 'with_holes',
                'depends': ['objective.approved.D-30.normal'],
                'setup': '_setup_kr_stale',
                'outputs': ['kr_id', 'checkin_id', 'last_checkin_date'],
            },
        })
        return catalog

    # ------------------------------------------------------------------
    def _new_objective(self, values):
        objective = self.env['aic.hrm.objective'].create(values)
        return self._track([objective])[0]

    def _new_kr(self, values):
        kr = self.env['aic.hrm.key.result'].create(values)
        return self._track([kr])[0]

    def _walk(self, objective, *states):
        for state in states:
            objective.write({'state': state})
        return objective

    def _setup_objective_empty(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        objective = self._new_objective({
            'name': 'UAT Objective Without Key Results',
            'cycle_id': cycle['cycle_id'], 'level': 'department',
            'department_id': org['dept_success_id'],
            'employee_id': org['manager_employee_id'],
            'weight': 25.0,
        })
        return {'objective_id': objective.id}

    def _setup_objective_normal(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        objective = self._new_objective({
            'name': 'UAT Ship the redesigned onboarding',
            'cycle_id': cycle['cycle_id'], 'level': 'department',
            'department_id': org['dept_product_id'],
            'employee_id': org['manager_employee_id'],
            'objective_type': 'committed', 'weight': 40.0,
        })
        number = self._new_kr({
            'name': 'UAT Activated accounts', 'objective_id': objective.id,
            'metric_type': 'number', 'direction': 'higher', 'unit': 'accounts',
            'baseline': 200.0, 'target': 1000.0, 'current': 480.0,
            'weight': 2.0,
        })
        percent = self._new_kr({
            'name': 'UAT Week-one retention', 'objective_id': objective.id,
            'metric_type': 'percent', 'direction': 'higher', 'unit': '%',
            'baseline': 40.0, 'target': 65.0, 'current': 52.0, 'weight': 1.0,
        })
        milestone = self._new_kr({
            'name': 'UAT Rollout milestones', 'objective_id': objective.id,
            'metric_type': 'milestone', 'direction': 'higher', 'weight': 1.0,
        })
        milestones = self.env['aic.hrm.kr.milestone'].create([
            {'kr_id': milestone.id, 'name': 'UAT Design signed off',
             'sequence': 10, 'weight': 1.0, 'is_done': True},
            {'kr_id': milestone.id, 'name': 'UAT Pilot with 20 customers',
             'sequence': 20, 'weight': 2.0, 'is_done': True},
            {'kr_id': milestone.id, 'name': 'UAT General availability',
             'sequence': 30, 'weight': 3.0, 'is_done': False},
        ])
        self._track(milestones)
        boolean = self._new_kr({
            'name': 'UAT Support playbook published',
            'objective_id': objective.id, 'metric_type': 'boolean',
            'direction': 'higher', 'target': 1.0, 'current': 0.0,
            'weight': 1.0,
        })
        # Key results have to exist before approval: after it, adding one is
        # refused and changing a target needs a revision.
        self._walk(objective, 'submitted', 'approved')
        return {
            'objective_id': objective.id,
            'kr_number_id': number.id,
            'kr_percent_id': percent.id,
            'kr_milestone_id': milestone.id,
            'kr_boolean_id': boolean.id,
            'milestone_ids': milestones.ids,
        }

    def _setup_objective_full(self, ctx):
        org, cycle = ctx['org.base.D0'], ctx['cycle.open.D-45']
        cycle_id = cycle['cycle_id']
        team = self.env['aic.hrm.team'].create({
            'name': 'UAT Onboarding Squad',
            'department_id': org['dept_product_id'],
            'lead_id': org['manager_employee_id'],
        })
        self._track([team])

        company = self._new_objective({
            'name': 'UAT Grow recurring revenue', 'cycle_id': cycle_id,
            'level': 'company', 'weight': 100.0,
            'employee_id': org['manager_employee_id'],
        })
        branch = self._new_objective({
            'name': 'UAT Grow revenue in the home market',
            'cycle_id': cycle_id, 'level': 'branch',
            'branch_id': org['company_id'], 'parent_id': company.id,
            'weight': 100.0, 'employee_id': org['manager_employee_id'],
        })
        department = self._new_objective({
            'name': 'UAT Product-led expansion', 'cycle_id': cycle_id,
            'level': 'department', 'department_id': org['dept_product_id'],
            'parent_id': branch.id, 'weight': 60.0,
            'employee_id': org['manager_employee_id'],
        })
        team_objective = self._new_objective({
            'name': 'UAT Squad: cut time-to-value', 'cycle_id': cycle_id,
            'level': 'team', 'team_id': team.id, 'parent_id': department.id,
            'weight': 50.0, 'employee_id': org['manager_employee_id'],
        })
        individual = self._new_objective({
            'name': 'UAT Redesign the first-run tour', 'cycle_id': cycle_id,
            'level': 'individual', 'employee_id': org['member_employee_id'],
            'parent_id': team_objective.id, 'weight': 100.0,
        })
        self._new_kr({
            'name': 'UAT Time to first value', 'objective_id': individual.id,
            'metric_type': 'number', 'direction': 'lower', 'unit': 'days',
            'baseline': 14.0, 'target': 5.0, 'current': 7.0, 'weight': 1.0,
        })
        for objective in (company, branch, department, team_objective,
                          individual):
            self._walk(objective, 'submitted', 'approved', 'in_progress',
                       'self_assessed', 'manager_review', 'done')
        return {
            'company_objective_id': company.id,
            'branch_objective_id': branch.id,
            'department_objective_id': department.id,
            'team_objective_id': team_objective.id,
            'individual_objective_id': individual.id,
            'team_id': team.id,
        }

    def _check_in(self, kr, day_offset, value, confidence, blocker=False):
        checkin = self.env['aic.hrm.checkin'].create({
            'kr_id': kr.id,
            'date': self._day(day_offset),
            'value_current': value,
            'confidence': confidence,
            'blocker': blocker,
        })
        return self._track([checkin])[0]

    def _setup_kr_checkins(self, ctx):
        parent = ctx['objective.approved.D-30.normal']
        kr = self.env['aic.hrm.key.result'].browse(parent['kr_number_id'])
        # Rising numbers with falling confidence: the shape a diagnosis is
        # supposed to notice, not a straight line up.
        checkins = [
            self._check_in(kr, -30, 320.0, 8),
            self._check_in(kr, -7, 430.0, 6),
            self._check_in(kr, 0, 480.0, 4,
                           blocker='UAT: waiting on the data pipeline'),
        ]
        return {
            'kr_id': kr.id,
            'checkin_ids': [c.id for c in checkins],
            'dates': [str(c.date) for c in checkins],
        }

    def _setup_kr_stale(self, ctx):
        parent = ctx['objective.approved.D-30.normal']
        kr = self.env['aic.hrm.key.result'].browse(parent['kr_percent_id'])
        checkin = self._check_in(kr, -30, 52.0, 5)
        return {'kr_id': kr.id, 'checkin_id': checkin.id,
                'last_checkin_date': str(checkin.date)}

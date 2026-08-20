# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The enterprise-scale lot.

CLAUDE.md commits the product to three numbers at 2,000 employees and 80,000
assignment lines: close a cycle in under 60s, import 10,000 rows in under
120s, draw the dashboard in under 3s. Those numbers had never been run against
a database that size, which means they were aspirations, not budgets.

This is deliberately not a fixture in the catalogue. Catalogue fixtures are
small, named and reversible; this one takes minutes and is measured, not
asserted. It reports the wall clock of each phase so the run can be compared
against the budget instead of described as "slow".
"""
import logging
import time

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH = 1000


class AicHrmUatFixtureScale(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def seed_scale(self, employees=2000, departments=40, kpis=40,
                   results_sample=0.1):
        """Generate the large lot and return per-phase timings in seconds.

        `results_sample` is the share of targets that also get three monthly
        results. Every target getting them would mean a quarter of a million
        rows for no extra signal - the aggregation path is already exercised
        by the sampled ones. The share is reported in the result so nobody
        reads the row count as full coverage.
        """
        self._check_enabled()
        if employees % departments:
            raise UserError(_(
                "Employees must divide evenly across departments; got "
                "%(employees)s over %(departments)s.",
                employees=employees, departments=departments))
        timings, marker = {}, [time.time()]

        def phase(name):
            now = time.time()
            timings[name] = round(now - marker[0], 2)
            marker[0] = now
            _logger.info("UAT scale phase %s: %ss", name, timings[name])

        Department = self.env['hr.department']
        Employee = self.env['hr.employee']
        Kpi = self.env['aic.hrm.kpi']
        Target = self.env['aic.hrm.kpi.target']
        Assignment = self.env['aic.hrm.kpi.assignment']
        Result = self.env['aic.hrm.kpi.period.result']

        cycle = self.env['aic.hrm.cycle'].create({
            'name': 'UAT Scale Year', 'code': 'UAT-SCALE',
            'cycle_type': 'year',
            'date_start': self._day(-120), 'date_end': self._day(245),
        })
        cycle.write({'state': 'open'})
        phase('cycle')

        department_records = Department.create([
            {'name': 'UAT Scale Division %02d' % index}
            for index in range(1, departments + 1)
        ])
        phase('departments')

        per_department = employees // departments
        employee_records = Employee.browse()
        for start in range(0, employees, BATCH):
            employee_records |= Employee.create([
                {'name': 'UAT Scale Employee %05d' % index,
                 'department_id': department_records[
                     (index - 1) // per_department].id}
                for index in range(start + 1,
                                   min(start + BATCH, employees) + 1)
            ])
        phase('employees')

        kpi_records = Kpi.create([
            {'name': 'UAT Scale KPI %02d' % index,
             'code': 'UAT-SCALE-%02d' % index,
             'direction': 'higher', 'aggregation': 'sum',
             'frequency': 'monthly', 'default_target': 100.0}
            for index in range(1, kpis + 1)
        ])
        phase('kpis')

        # One target per employee per KPI: 2,000 x 40 = 80,000 lines, which is
        # the number the budget is written against.
        target_values = [
            {'kpi_id': kpi.id, 'cycle_id': cycle.id,
             'employee_id': employee.id, 'target_value': 100.0,
             'weight': round(100.0 / kpis, 4)}
            for employee in employee_records
            for kpi in kpi_records
        ]
        targets = Target.browse()
        for start in range(0, len(target_values), BATCH):
            targets |= Target.create(target_values[start:start + BATCH])
        phase('targets')

        by_employee = {}
        for target in targets:
            by_employee.setdefault(target.employee_id.id, []).append(target.id)
        assignment_values = [
            {'employee_id': employee_id, 'cycle_id': cycle.id,
             'line_ids': [(0, 0, {'kpi_target_id': target_id,
                                  'weight': round(100.0 / kpis, 4)})
                          for target_id in target_ids]}
            for employee_id, target_ids in by_employee.items()
        ]
        for start in range(0, len(assignment_values), 100):
            Assignment.create(assignment_values[start:start + 100])
        phase('assignments')

        sampled = targets[:int(len(targets) * results_sample)]
        result_values = []
        for target in sampled:
            for month in range(3):
                first = self._month(-month).replace(day=1)
                result_values.append({
                    'kpi_target_id': target.id,
                    'date_from': first,
                    'date_to': self._month(-month + 1).replace(day=1),
                    'actual': 60.0 + month * 10,
                    'state': 'confirmed', 'source': 'manual',
                })
        for start in range(0, len(result_values), BATCH):
            Result.create(result_values[start:start + BATCH])
        phase('period_results')

        return {
            'cycle_id': cycle.id,
            'counts': {
                'departments': len(department_records),
                'employees': len(employee_records),
                'kpis': len(kpi_records),
                'targets': len(targets),
                'assignment_lines': len(target_values),
                'period_results': len(result_values),
                'results_sample': results_sample,
            },
            'timings': timings,
        }

    @api.model
    def drop_scale(self):
        """Remove the large lot again.

        Not tracked in the fixture ledger on purpose: writing 200,000 ledger
        rows to be able to delete 200,000 records doubles the cost of the
        exercise for nothing. The lot is identifiable instead - one cycle
        code, one name prefix - and this is the one place that knows it.
        """
        self._check_enabled()
        removed = {}
        cycle = self.env['aic.hrm.cycle'].search([('code', '=', 'UAT-SCALE')])
        if cycle:
            targets = self.env['aic.hrm.kpi.target'].search(
                [('cycle_id', '=', cycle.id)])
            results = self.env['aic.hrm.kpi.period.result'].search(
                [('kpi_target_id', 'in', targets.ids)])
            assignments = self.env['aic.hrm.kpi.assignment'].search(
                [('cycle_id', '=', cycle.id)])
            removed['period_results'] = len(results)
            results.unlink()
            removed['assignments'] = len(assignments)
            assignments.unlink()
            removed['targets'] = len(targets)
            targets.unlink()
            cycle._write({'state': 'draft'})
            cycle.invalidate_recordset(['state'])
            removed['cycles'] = len(cycle)
            cycle.unlink()

        for model, domain in (
            ('aic.hrm.kpi', [('code', 'like', 'UAT-SCALE-%')]),
            ('hr.employee', [('name', 'like', 'UAT Scale Employee%')]),
            ('hr.department', [('name', 'like', 'UAT Scale Division%')]),
        ):
            records = self.env[model].with_context(active_test=False).search(domain)
            removed[model] = len(records)
            records.unlink()
        return removed

    @api.model
    def measure_budgets(self, cycle_id):
        """Time the three operations CLAUDE.md puts a number on."""
        self._check_enabled()
        cycle = self.env['aic.hrm.cycle'].browse(cycle_id)
        measured = {}

        start = time.time()
        self.env['aic.hrm.kpi.assignment'].search(
            [('cycle_id', '=', cycle.id)]).mapped('score')
        measured['score_rollup'] = round(time.time() - start, 2)

        start = time.time()
        self.env['aic.hrm.progress.report'].formatted_read_group(
            [('cycle_id', '=', cycle.id)],
            groupby=['department_id'],
            aggregates=['achieved:avg', 'expected:avg', '__count'])
        measured['dashboard_group'] = round(time.time() - start, 2)

        start = time.time()
        cycle.write({'state': 'review'})
        cycle.write({'state': 'closed'})
        measured['close_cycle'] = round(time.time() - start, 2)

        return measured

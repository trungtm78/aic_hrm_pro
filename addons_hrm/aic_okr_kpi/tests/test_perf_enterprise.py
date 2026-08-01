# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Enterprise-scale performance budgets (2A).

Fixture mirrors the real deployment shape scaled up: N employees, a shared
KPI library, ~40 scorecard lines per person. Runs under the dedicated `perf`
tag only — far too heavy for the regular CI loop:

    python odoo-bin -c odoo.conf -d <db> -u aic_okr_kpi \
        --test-enable --test-tags perf --stop-after-init

Budgets (documented in the spec): bulk period-result ingestion + full
recompute < 60s; department dashboard query < 3s.
"""
import os
import time

from odoo.tests import TransactionCase, tagged

SCALE_EMPLOYEES = int(os.environ.get('AIC_HRM_PERF_EMPLOYEES', '2000'))
KPIS_PER_EMPLOYEE = 40
# Spec budgets (2A): close-cycle recompute < 60s, importing 10k period rows
# < 120s, dashboard queries < 3s.
CLOSE_RECOMPUTE_BUDGET_S = 60.0
IMPORT_ROWS = 10000
IMPORT_BUDGET_S = 120.0
DASHBOARD_BUDGET_S = 3.0


@tagged('perf', '-at_install', 'post_install')
class TestEnterprisePerformance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.cycle = env['aic.hrm.cycle'].create({
            'name': 'Perf FY', 'code': 'PERF-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        cls.department = env['hr.department'].create({'name': 'Perf Dept'})
        kpis = env['aic.hrm.kpi'].create([
            {'name': f'Perf KPI {i}', 'code': f'PERF-KPI-{i:02d}',
             'direction': 'higher', 'aggregation': 'last'}
            for i in range(KPIS_PER_EMPLOYEE)])
        employees = env['hr.employee'].create([
            {'name': f'Perf Employee {i}',
             'department_id': cls.department.id}
            for i in range(SCALE_EMPLOYEES)])
        target_vals = []
        for employee in employees:
            for kpi in kpis:
                target_vals.append({
                    'kpi_id': kpi.id, 'cycle_id': cls.cycle.id,
                    'employee_id': employee.id, 'target_value': 100.0,
                    'weight': 2.5,
                })
        cls.targets = env['aic.hrm.kpi.target'].create(target_vals)
        line_weight = 100.0 / KPIS_PER_EMPLOYEE
        assignment_vals = []
        target_index = 0
        for employee in employees:
            lines = []
            for _k in range(KPIS_PER_EMPLOYEE):
                lines.append((0, 0, {
                    'kpi_target_id': cls.targets[target_index].id,
                    'weight': line_weight,
                }))
                target_index += 1
            assignment_vals.append({
                'employee_id': employee.id, 'cycle_id': cls.cycle.id,
                'line_ids': lines,
            })
        cls.assignments = env['aic.hrm.kpi.assignment'].create(
            assignment_vals)
        # Seed one confirmed month for every target (line count = employees
        # x KPIs). Not timed: it represents data accumulated over the cycle.
        env['aic.hrm.kpi.period.result'].create([{
            'kpi_target_id': target.id,
            'date_from': '2026-01-01', 'date_to': '2026-01-31',
            'actual': 80.0, 'state': 'confirmed',
        } for target in cls.targets])
        env.flush_all()

    def test_close_cycle_recompute_budget(self):
        """Closing a cycle re-validates every score: full recompute of the
        target -> line -> assignment chain across the whole population."""
        self.env.invalidate_all()
        started = time.monotonic()
        self.targets.modified(['target_value'])
        self.env.flush_all()
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, CLOSE_RECOMPUTE_BUDGET_S,
            f"full recompute of {len(self.targets)} targets took "
            f"{elapsed:.1f}s (budget {CLOSE_RECOMPUTE_BUDGET_S}s)")
        self.assertAlmostEqual(self.assignments[0].score, 0.8, places=2)

    def test_import_burst_budget(self):
        """Importing a month of actuals (10k rows) within the import budget."""
        subset = self.targets[:IMPORT_ROWS]
        result_vals = [{
            'kpi_target_id': target.id,
            'date_from': '2026-02-01', 'date_to': '2026-02-28',
            'actual': 90.0, 'state': 'confirmed',
        } for target in subset]
        started = time.monotonic()
        self.env['aic.hrm.kpi.period.result'].create(result_vals)
        self.env.flush_all()
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, IMPORT_BUDGET_S,
            f"importing {len(result_vals)} period results took "
            f"{elapsed:.1f}s (budget {IMPORT_BUDGET_S}s)")

    def test_dashboard_query_budget(self):
        self.env.flush_all()
        started = time.monotonic()
        self.env['aic.hrm.department.scorecard'].search([
            ('cycle_id', '=', self.cycle.id)])
        self.env['aic.hrm.kpi.assignment']._read_group(
            [('cycle_id', '=', self.cycle.id)],
            ['department_id'], ['score:avg'])
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, DASHBOARD_BUDGET_S,
            f"dashboard queries took {elapsed:.2f}s "
            f"(budget {DASHBOARD_BUDGET_S}s)")

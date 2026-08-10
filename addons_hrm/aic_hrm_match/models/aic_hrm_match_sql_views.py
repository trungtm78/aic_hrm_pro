# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""SQL views for reporting — computed tables with _auto=False."""
from odoo import fields, models


class AicHrmMatchCapacityReport(models.Model):
    _name = 'aic.hrm.match.capacity.report'
    _description = 'Capacity Report'
    _auto = False
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', readonly=True)
    week_start = fields.Date('Week Start', readonly=True)
    gross_hours = fields.Float('Gross Hours', readonly=True)
    booked_hours = fields.Float('Booked Hours', readonly=True)
    free_hours = fields.Float('Free Hours', readonly=True)
    utilization_pct = fields.Float('Utilization %', readonly=True)

    def init(self):
        """Build the underlying SQL view."""
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                emp.id as id,
                emp.id as employee_id,
                DATE_TRUNC('week', alloc.date_start)::date as week_start,
                COALESCE(SUM(EXTRACT(epoch FROM (alloc.date_end - alloc.date_start))) / 3600.0, 0) as booked_hours,
                0 as gross_hours,
                0 as free_hours,
                ROUND(100.0 * COALESCE(SUM(EXTRACT(epoch FROM (alloc.date_end - alloc.date_start))) / 3600.0, 0) / 40.0, 1) as utilization_pct
            FROM hr_employee emp
            LEFT JOIN aic_hrm_match_allocation alloc 
                ON emp.id = alloc.employee_id 
                AND alloc.state IN ('proposed', 'confirmed', 'done')
            GROUP BY emp.id, week_start
            ORDER BY week_start DESC, emp.id
        """)


class AicHrmMatchFairnessReport(models.Model):
    _name = 'aic.hrm.match.fairness.report'
    _description = 'Fairness Report'
    _auto = False

    run_id = fields.Many2one('aic.hrm.match.run', readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True)
    selection_count = fields.Integer('Times Selected', readonly=True)
    average_score = fields.Float('Average Score', readonly=True)
    last_selected = fields.Datetime('Last Selected', readonly=True)

    def init(self):
        """Build the underlying SQL view."""
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY run.id) as id,
                run.id as run_id,
                cand.employee_id,
                COUNT(DISTINCT run.id) as selection_count,
                AVG(cand.total_score) as average_score,
                MAX(run.create_date) as last_selected
            FROM aic_hrm_match_candidate cand
            JOIN aic_hrm_match_run run ON cand.run_id = run.id
            WHERE cand.employee_id IS NOT NULL
            GROUP BY run.id, cand.employee_id
            ORDER BY selection_count DESC
        """)


class AicHrmMatchSkillDemandReport(models.Model):
    _name = 'aic.hrm.match.skill.demand.report'
    _description = 'Skill Demand Report'
    _auto = False

    skill_id = fields.Many2one('hr.skill', readonly=True)
    skill_type_id = fields.Many2one('hr.skill.type', readonly=True)
    requested_count = fields.Integer('Times Requested', readonly=True)
    available_count = fields.Integer('People With Skill', readonly=True)
    gap = fields.Integer('Gap', readonly=True, compute='_compute_gap')

    def _compute_gap(self):
        for rec in self:
            rec.gap = rec.requested_count - rec.available_count

    def init(self):
        """Build the underlying SQL view."""
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY skill.id) as id,
                skill.id as skill_id,
                skill.skill_type_id,
                COUNT(DISTINCT slot_skill.slot_id) as requested_count,
                COUNT(DISTINCT emp_skill.id) as available_count
            FROM hr_skill skill
            LEFT JOIN aic_hrm_match_request_slot_skill slot_skill 
                ON skill.id = slot_skill.skill_id
            LEFT JOIN hr_employee_skill emp_skill 
                ON skill.id = emp_skill.skill_id
            GROUP BY skill.id, skill.skill_type_id
            ORDER BY requested_count DESC
        """)

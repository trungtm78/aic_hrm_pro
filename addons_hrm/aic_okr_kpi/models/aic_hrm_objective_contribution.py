# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Who is carrying a department objective, and how they are doing on it.

Every KPI target already names the key result it serves, and the customer's
own import fills that in - 409 of their 418 targets carry the link. Nothing
read it back: a director could see the objective's score and each person's
scorecard score, but never the line between them. Asked "who is carrying
this objective and how are they doing", the system had no answer.

One row is one person on one objective in one cycle. The measure is the
weight of their own scorecard they committed to it and what they scored on
the part that has figures - the same pair the scorecards and the leadership
desk use, so the three screens agree.

The numbers do not add up across people, and the report says so: the same
revenue figure is deliberately carried by several people at once (three of
them share the 38,03 tỷ Telco line), because that is shared accountability,
not a split. Summing the rows would count the department's revenue twice.
"""
from odoo import fields, models, tools


class AicHrmObjectiveContribution(models.Model):
    """Read-only roll-up backed by a SQL view, like the department scorecard:
    always current, nothing stored, safe at enterprise row counts."""
    _name = 'aic.hrm.objective.contribution'
    _description = 'Contribution to Objective'
    _auto = False
    _order = 'cycle_id desc, objective_id, weight desc'
    _rec_name = 'employee_id'

    cycle_id = fields.Many2one('aic.hrm.cycle', readonly=True)
    objective_id = fields.Many2one('aic.hrm.objective', readonly=True)
    kr_id = fields.Many2one('aic.hrm.key.result', string='Key Result', readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True)
    department_id = fields.Many2one('hr.department', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    target_count = fields.Integer(
        string='KPIs', readonly=True,
        help="How many of this person's KPIs serve the objective.")
    weight = fields.Float(
        string='Weight Committed', readonly=True, aggregator='sum',
        help="Share of this person's scorecard, out of 100, that serves the "
             "objective. It says how much of their month the objective is.")
    measured_weight = fields.Float(
        string='Weight With Figures', readonly=True, aggregator='sum',
        help="Part of that weight whose KPIs have confirmed actuals.")
    coverage = fields.Float(
        string='Data Coverage (%)', readonly=True, aggregator='avg',
        help="Share of the committed weight that has figures behind it.")
    score_covered = fields.Float(
        string='Score on Measured KPIs', readonly=True, aggregator='avg',
        help="Weighted score over the KPIs that have figures. Read it "
             "together with the coverage.")
    score = fields.Float(
        string='Score', readonly=True, aggregator='avg',
        help="Weighted score over the whole committed weight, counting a KPI "
             "still waiting for its figure as zero.")

    def init(self):
        # Built from the scorecard lines rather than from the targets: the
        # line weight is what the person is actually scored on, and it is
        # the line that knows whether the figure has been confirmed.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    -- A stable id per group: row_number() changes between
                    -- queries, so a row just searched could be read back as
                    -- a different person.
                    MIN(l.id) AS id,
                    a.cycle_id AS cycle_id,
                    t.objective_id AS objective_id,
                    t.kr_id AS kr_id,
                    a.employee_id AS employee_id,
                    a.department_id AS department_id,
                    a.company_id AS company_id,
                    COUNT(*) AS target_count,
                    SUM(l.weight) AS weight,
                    SUM(l.weight) FILTER (WHERE l.has_actual) AS measured_weight,
                    CASE WHEN SUM(l.weight) > 0
                         THEN 100.0 * COALESCE(SUM(l.weight)
                                               FILTER (WHERE l.has_actual), 0)
                              / SUM(l.weight)
                         ELSE 0 END AS coverage,
                    CASE WHEN COALESCE(SUM(l.weight)
                                       FILTER (WHERE l.has_actual), 0) > 0
                         THEN SUM(l.score * l.weight) FILTER (WHERE l.has_actual)
                              / SUM(l.weight) FILTER (WHERE l.has_actual)
                         ELSE 0 END AS score_covered,
                    CASE WHEN SUM(l.weight) > 0
                         THEN SUM(l.score * l.weight) / SUM(l.weight)
                         ELSE 0 END AS score
                FROM aic_hrm_kpi_assignment_line l
                JOIN aic_hrm_kpi_assignment a ON a.id = l.assignment_id
                JOIN aic_hrm_kpi_target t     ON t.id = l.kpi_target_id
                WHERE t.objective_id IS NOT NULL
                GROUP BY a.cycle_id, t.objective_id, t.kr_id, a.employee_id,
                         a.department_id, a.company_id
            )
        """)

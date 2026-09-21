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
from odoo import api, fields, models, tools


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

    @api.model
    def carriers_for_cycle(self, cycle_id):
        """Who carries each key result of this cycle's objectives, one entry
        per person.

        The report keeps a row per month, because a director asks it what
        happened in August. The alignment tree asks a different question -
        who is carrying this quarterly key result - and reading the rows raw
        answered it with the same person once per monthly scorecard, three
        entries deep with three different scores. Here the months are folded
        back into the person they belong to.

        Weight is averaged, never added: it is a share of one scorecard out
        of 100, so three months at 80 is 80 of an average month, not 240 of
        100. The score stays weighted over the part that has figures, and the
        count of periods still waiting is carried alongside so a carrier who
        looks green on two months out of three does not look finished.
        """
        # Through the same cycles the tree draws, so a month shows the
        # carriers of the quarter it is working towards rather than nothing.
        Objective = self.env['aic.hrm.objective']
        scope = Objective.alignment_scope(cycle_id)
        objectives = Objective.search([('cycle_id', 'in', scope['cycle_ids'])])
        if not objectives:
            return []
        rows = self.search_read(
            [('objective_id', 'in', objectives.ids)],
            ['cycle_id', 'objective_id', 'kr_id', 'employee_id', 'target_count',
             'weight', 'measured_weight', 'score_covered'])
        folded = {}
        for row in rows:
            key = (row['kr_id'] and row['kr_id'][0], row['employee_id'][0])
            entry = folded.get(key)
            if entry is None:
                entry = folded[key] = {
                    'kr_id': row['kr_id'] and row['kr_id'][0] or False,
                    'objective_id': row['objective_id'][0],
                    'employee_id': row['employee_id'][0],
                    'employee_name': row['employee_id'][1],
                    'target_count': 0,
                    'periods': 0,
                    'measured_periods': 0,
                    'weight': 0.0,
                    'measured_weight': 0.0,
                    'score_covered': 0.0,
                    'coverage': 0.0,
                }
            entry['periods'] += 1
            entry['target_count'] = max(entry['target_count'], row['target_count'])
            entry['weight'] += row['weight']
            measured = row['measured_weight'] or 0.0
            if measured:
                entry['measured_periods'] += 1
                entry['measured_weight'] += measured
                entry['score_covered'] += row['score_covered'] * measured
        entries = []
        for entry in folded.values():
            committed = entry.pop('weight')
            measured = entry['measured_weight']
            entry['weight'] = committed / entry['periods']
            entry['coverage'] = 100.0 * measured / committed if committed else 0.0
            entry['score_covered'] = entry['score_covered'] / measured if measured else 0.0
            entries.append(entry)
        entries.sort(key=lambda entry: (-entry['weight'], entry['employee_name']))
        return entries

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

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, tools

# Where a measurement should stand if the goal moved linearly across the
# cycle calendar, evaluated AT THE DATE OF THE MEASUREMENT.
#
# This is computed here rather than read from
# aic.hrm.key.result.expected_progress for two reasons. That field is a
# non-stored compute, so a view cannot see it - but the deciding reason is
# that it answers "is this on pace today", while a report has to answer
# "was this on pace then". Same linear rule as _compute_pace, different
# moment.
#
# NULLIF guards a cycle whose dates are not set yet; the clamp keeps a
# measurement dated outside the cycle from reporting more than a full
# calendar spent.
ELAPSED = """
    LEAST(1.0, GREATEST(0.0,
        ({when} - c.date_start)::numeric
        / NULLIF(c.date_end - c.date_start, 0)))
"""

# Achievement follows the KPI's direction and is capped by the cycle, so a
# runaway actual cannot drag an average into nonsense.
ACHIEVEMENT = """
    LEAST(COALESCE(c.score_cap, 1.0), GREATEST(0.0,
        CASE
            WHEN COALESCE(t.target_value, 0) = 0 THEN 0.0
            WHEN t.direction = 'lower'
                THEN 2.0 - pr.actual / NULLIF(t.target_value, 0)
            ELSE pr.actual / NULLIF(t.target_value, 0)
        END))
"""


class AicHrmProgressReport(models.Model):
    """Progress against plan, over time, as one analysable table.

    Every row is one measurement of one thing on one date. Two sources
    feed it and neither is new - the data was already being recorded:

      * check-ins, which store ``progress_snapshot`` against a date, so
        every key result has carried its own history from day one;
      * confirmed KPI period results, an actual against a target between
        two dates.

    Unioning them is sound because both sides are normalised 0..1 ratios:
    the same unit, so averaging across them means something. ``kind``
    separates them again for a reader who wants only one.
    """
    _name = 'aic.hrm.progress.report'
    _description = 'Progress Against Plan'
    _auto = False
    _order = 'date desc'
    _rec_name = 'label'

    date = fields.Date(readonly=True)
    kind = fields.Selection([
        ('kr', 'Key result'),
        ('kpi', 'KPI'),
    ], readonly=True)
    label = fields.Char(string='Measured', readonly=True)

    cycle_id = fields.Many2one('aic.hrm.cycle', readonly=True)
    objective_id = fields.Many2one('aic.hrm.objective', readonly=True)
    kr_id = fields.Many2one('aic.hrm.key.result', readonly=True)
    kpi_target_id = fields.Many2one('aic.hrm.kpi.target', readonly=True)

    employee_id = fields.Many2one('hr.employee', string='Owner',
                                  readonly=True)
    department_id = fields.Many2one('hr.department', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position', readonly=True)
    level = fields.Selection([
        ('company', 'Company'),
        ('branch', 'Branch'),
        ('department', 'Department'),
        ('team', 'Team'),
        ('individual', 'Individual'),
    ], readonly=True)
    objective_type = fields.Selection([
        ('committed', 'Committed'),
        ('aspirational', 'Aspirational'),
    ], readonly=True)
    perspective_id = fields.Many2one(
        'aic.hrm.perspective', string='Perspective', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    achieved = fields.Float(
        string='Achieved', readonly=True, aggregator='avg',
        help="Normalised progress on that date, 0..1.")
    expected = fields.Float(
        string='Expected', readonly=True, aggregator='avg',
        help="Where it should have stood on that date if it moved "
             "linearly across the cycle calendar.")
    gap = fields.Float(
        string='Gap', readonly=True, aggregator='avg',
        help="Achieved minus expected. Negative means behind plan.")
    weight = fields.Float(readonly=True, aggregator='sum')
    rag = fields.Selection([
        ('green', 'On track'),
        ('amber', 'At risk'),
        ('red', 'Off track'),
        ('none', 'Not scored'),
    ], readonly=True)

    # A SQL view reads the database, and Odoo does not know this model
    # depends on the tables underneath it - so a check-in recorded a moment
    # ago is still sitting in the ORM cache when the report is opened, and
    # the reader sees the figure from before their own entry. Flushing the
    # sources first costs nothing and removes a whole class of "the report
    # is wrong" support tickets.
    _SOURCE_MODELS = (
        'aic.hrm.checkin',
        'aic.hrm.kpi.period.result',
        'aic.hrm.key.result',
        'aic.hrm.kpi.target',
        'aic.hrm.objective',
        'aic.hrm.cycle',
        # Odoo 19 keeps the job position on hr.version, which the view
        # joins through hr_employee.current_version_id.
        'hr.employee',
        'hr.version',
    )

    def _flush_sources(self):
        for model in self._SOURCE_MODELS:
            self.env[model].flush_model()

    def _search(self, domain, *args, **kwargs):
        self._flush_sources()
        return super()._search(domain, *args, **kwargs)

    def _read_group(self, domain, groupby=(), aggregates=(), *args, **kwargs):
        self._flush_sources()
        return super()._read_group(domain, groupby, aggregates,
                                   *args, **kwargs)

    def _extra_select(self):
        """Columns an optional layer above this module contributes.

        The library sits ABOVE okr_kpi in the dependency graph, so this
        model cannot name aic.hrm.library.role - reversing the dependency
        would make a cycle. Each entry is a full "expression AS name" and
        is spliced into both halves of the union, so an extending module
        adds a dimension without restating the query.
        """
        return []

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        indent = '\n' + ' ' * 24
        extra = ''.join(indent + column + ','
                        for column in self._extra_select())
        elapsed_kr = ELAPSED.format(when='ci.date')
        elapsed_kpi = ELAPSED.format(when='pr.date_to')
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                -- The id is derived from the source row, not from
                -- row_number(). row_number() over a non-unique ORDER BY
                -- assigns ids that shift between executions, and the ORM
                -- reads a record in a second query after the search: the
                -- reader then gets a different row than the one found.
                -- Interleaving by parity keeps both sources unique and
                -- stable for as long as the source row exists.
                SELECT d.*
                FROM (
                    SELECT
                        ci.id * 2                           AS id,
                        ci.date                             AS date,
                        'kr'::varchar                       AS kind,
                        kr.name                             AS label,
                        kr.cycle_id                         AS cycle_id,
                        kr.objective_id                     AS objective_id,
                        kr.id                               AS kr_id,
                        NULL::integer                       AS kpi_target_id,
                        kr.employee_id                      AS employee_id,
                        COALESCE(kr.department_id, o.department_id)
                                                            AS department_id,
                        ver.job_id                          AS job_id,{extra}
                        o.level                             AS level,
                        o.objective_type                    AS objective_type,
                        o.perspective_id                    AS perspective_id,
                        ci.company_id                       AS company_id,
                        COALESCE(ci.progress_snapshot, 0.0) AS achieved,
                        {elapsed_kr}                        AS expected,
                        COALESCE(ci.progress_snapshot, 0.0)
                            - {elapsed_kr}                  AS gap,
                        COALESCE(kr.weight, 0.0)            AS weight,
                        COALESCE(ci.rag_snapshot, 'none')   AS rag
                    FROM aic_hrm_checkin ci
                    JOIN aic_hrm_key_result kr    ON kr.id = ci.kr_id
                    JOIN aic_hrm_objective o      ON o.id = kr.objective_id
                    JOIN aic_hrm_cycle c          ON c.id = kr.cycle_id
                    LEFT JOIN hr_employee emp     ON emp.id = kr.employee_id
                    LEFT JOIN hr_version ver      ON ver.id = emp.current_version_id
                    WHERE ci.kr_id IS NOT NULL

                    UNION ALL

                    SELECT
                        pr.id * 2 + 1                       AS id,
                        pr.date_to                          AS date,
                        'kpi'::varchar                      AS kind,
                        kpi.name                            AS label,
                        t.cycle_id                          AS cycle_id,
                        t.objective_id                      AS objective_id,
                        NULL::integer                       AS kr_id,
                        t.id                                AS kpi_target_id,
                        t.employee_id                       AS employee_id,
                        COALESCE(t.department_id, o.department_id)
                                                            AS department_id,
                        ver.job_id                          AS job_id,{extra}
                        o.level                             AS level,
                        o.objective_type                    AS objective_type,
                        COALESCE(t.perspective_id, o.perspective_id)
                                                            AS perspective_id,
                        pr.company_id                       AS company_id,
                        {ACHIEVEMENT}                       AS achieved,
                        {elapsed_kpi}                       AS expected,
                        {ACHIEVEMENT} - {elapsed_kpi}       AS gap,
                        COALESCE(t.weight, 0.0)             AS weight,
                        'none'::varchar                     AS rag
                    FROM aic_hrm_kpi_period_result pr
                    JOIN aic_hrm_kpi_target t     ON t.id = pr.kpi_target_id
                    JOIN aic_hrm_kpi kpi          ON kpi.id = t.kpi_id
                    JOIN aic_hrm_cycle c          ON c.id = t.cycle_id
                    LEFT JOIN aic_hrm_objective o ON o.id = t.objective_id
                    LEFT JOIN hr_employee emp     ON emp.id = t.employee_id
                    LEFT JOIN hr_version ver      ON ver.id = emp.current_version_id
                    -- A draft number is somebody's working note, not a
                    -- result; a management report must not read it.
                    WHERE pr.state = 'confirmed'
                ) d
            )
        """)

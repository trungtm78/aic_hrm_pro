# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Data repairs shared by the module's upgrade scripts.

They live here, not in the scripts, so the tests can run exactly what an
upgrade runs: a migration script is loaded by file path and nothing else can
import it.
"""
import logging

_logger = logging.getLogger(__name__)

# Stored computes whose reading depends on whether anything was measured.
# Deepest first, so a parent is recomputed from settled children.
MEASUREMENT_FIELDS = [
    ('aic.hrm.key.result', ['has_actual', 'score', 'rag']),
    ('aic.hrm.kpi.target', ['has_actual', 'score', 'rag']),
    ('aic.hrm.objective', ['score', 'data_coverage', 'score_covered', 'rag']),
    ('aic.hrm.kpi.assignment.line', ['has_actual', 'score']),
    ('aic.hrm.kpi.assignment', ['score', 'data_coverage', 'score_covered',
                                'rag']),
]


def recompute_measurement(env):
    """Re-read the stored scores after a change in what counts as measured.

    A changed compute does not touch rows already in the database; without
    this an upgraded customer keeps the verdict the old formula stored."""
    for model_name, names in MEASUREMENT_FIELDS:
        model = env.get(model_name)
        if model is None:
            continue
        records = model.with_context(active_test=False).search([])
        if not records:
            continue
        for name in names:
            field = model._fields.get(name)
            if field is not None and field.store and field.compute:
                env.add_to_compute(field, records)
        env.flush_all()
        _logger.info("Recomputed %s on %s %s record(s).",
                     ', '.join(names), len(records), model_name)


def backfill_progress_reported(env):
    """Recover when progress was reported on key results written before the
    moment was stamped.

    The evidence is what the database already holds: the latest check-in,
    and every change of the current value in the key result's tracked
    history. A key result with neither was never reported, whatever its
    value - which is the point."""
    env.flush_all()
    env.cr.execute("""
        WITH reports AS (
            SELECT m.res_id AS kr_id, MAX(m.date) AS reported_on
              FROM mail_tracking_value v
              JOIN mail_message m ON m.id = v.mail_message_id
              JOIN ir_model_fields f ON f.id = v.field_id
             WHERE m.model = 'aic.hrm.key.result'
               AND f.model = 'aic.hrm.key.result'
               AND f.name = 'current'
             GROUP BY m.res_id
            UNION ALL
            SELECT id, last_checkin_date::timestamp
              FROM aic_hrm_key_result
             WHERE last_checkin_date IS NOT NULL
        )
        UPDATE aic_hrm_key_result kr
           SET progress_reported_on = latest.reported_on
          FROM (SELECT kr_id, MAX(reported_on) AS reported_on
                  FROM reports GROUP BY kr_id) latest
         WHERE kr.id = latest.kr_id
           AND kr.progress_reported_on IS NULL
     RETURNING kr.id
    """)
    ids = [row[0] for row in env.cr.fetchall()]
    env['aic.hrm.key.result'].invalidate_model(['progress_reported_on'])
    _logger.info("Progress report dates recovered on %s key result(s).",
                 len(ids))
    return ids

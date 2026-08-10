# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Performance score from OKR/KPI achievements when aic_okr_kpi is installed.

Scorer: performance_score
- Raw value: weighted average of historic Key Result achievements
- Source: Key Results linked to tasks the employee worked on
- Evidence: count and average score of KRs
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AicHrmMatchOkrBridge(models.AbstractModel):
    _name = 'aic.hrm.match.scorer'
    _inherit = 'aic.hrm.match.scorer'

    @api.model
    def _prefetch_performance_score(self, ctx):
        """Load Key Result scores for the whole pool, once."""
        Task = self.env['project.task']
        tasks = Task.search([
            ('aic_hrm_assignment_ids.employee_id', 'in', ctx.scoped_ids)
        ])
        performance_scores = {emp_id: [] for emp_id in ctx.scoped_ids}
        for task in tasks:
            if not task.aic_kr_id or task.aic_kr_id.score is None:
                continue
            for assignment in task.aic_hrm_assignment_ids:
                if assignment.employee_id.id in performance_scores:
                    performance_scores[assignment.employee_id.id].append(task.aic_kr_id.score)
        ctx.data['performance_scores'] = performance_scores

    @api.model
    def _score_performance_score(self, ctx):
        """Raw score: weighted average of Key Result achievement."""
        scores = {}
        perf_scores = ctx.data.get('performance_scores', {})
        for employee_id in ctx.scoped_ids:
            kr_scores = perf_scores.get(employee_id, [])
            if not kr_scores:
                scores[employee_id] = None
                continue
            avg_score = sum(kr_scores) / len(kr_scores)
            scores[employee_id] = avg_score
            ctx.add_evidence(employee_id, 'performance_score', f'{len(kr_scores)} KRs, avg {avg_score:.1%}')
        return scores

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

# Task states that count as delivered / as removed from scope.
_DONE_STATES = ('1_done',)
_CANCELLED_STATES = ('1_canceled',)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    aic_kr_id = fields.Many2one(
        'aic.hrm.key.result', string='Key Result', index=True,
        ondelete='set null',
        help="Key result this task delivers against. With an automatic "
             "progress mode on the key result, closing the task moves the "
             "score.")

    def write(self, vals):
        # Capture KRs on BOTH sides of a relink so each resyncs.
        krs_before = self.mapped('aic_kr_id')
        result = super().write(vals)
        if {'state', 'aic_kr_id', 'active'} & set(vals):
            (krs_before | self.mapped('aic_kr_id'))._sync_task_progress()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks.mapped('aic_kr_id')._sync_task_progress()
        return tasks

    def unlink(self):
        krs = self.mapped('aic_kr_id')
        result = super().unlink()
        krs._sync_task_progress()
        return result


class AicHrmKeyResult(models.Model):
    _inherit = 'aic.hrm.key.result'

    task_ids = fields.One2many('project.task', 'aic_kr_id', string='Tasks')
    task_count = fields.Integer(compute='_compute_task_stats')
    task_done_count = fields.Integer(compute='_compute_task_stats')
    task_progress_mode = fields.Selection([
        ('off', 'Manual figures'),
        ('count_done', 'Current = tasks done'),
        ('percent_done', 'Current = % of tasks done'),
    ], default='off', required=True,
        help="Automatic actuals from linked project tasks. 'Manual' never "
             "touches your figures.")

    @api.depends('task_ids', 'task_ids.state')
    def _compute_task_stats(self):
        for kr in self:
            live = kr.task_ids.filtered(
                lambda t: t.state not in _CANCELLED_STATES)
            kr.task_count = len(kr.task_ids)
            kr.task_done_count = len(live.filtered(
                lambda t: t.state in _DONE_STATES))

    def _sync_task_progress(self):
        """Write task-derived actuals into `current` for automatic modes.

        Goes through write() so the whole scoring chain (progress, RAG,
        objective roll-up, scorecards) reacts exactly as a manual check-in
        would.
        """
        for kr in self.filtered(lambda k: k.task_progress_mode != 'off'):
            live = kr.task_ids.filtered(
                lambda t: t.state not in _CANCELLED_STATES)
            done = len(live.filtered(lambda t: t.state in _DONE_STATES))
            if kr.task_progress_mode == 'count_done':
                current = float(done)
            else:  # percent_done
                current = 100.0 * done / len(live) if live else 0.0
            kr.write({'current': current})

    def write(self, vals):
        result = super().write(vals)
        if 'task_progress_mode' in vals:
            self._sync_task_progress()
        return result

    @api.model
    def _cron_sync_task_progress(self):
        """Daily safety net for changes that bypassed the ORM hooks."""
        self.search([
            ('task_progress_mode', '!=', 'off'),
            ('cycle_id.state', '=', 'open'),
        ])._sync_task_progress()
        # Also catch KRs in cycles not yet opened (draft planning boards).
        self.search([
            ('task_progress_mode', '!=', 'off'),
            ('cycle_id.state', '=', 'draft'),
        ])._sync_task_progress()

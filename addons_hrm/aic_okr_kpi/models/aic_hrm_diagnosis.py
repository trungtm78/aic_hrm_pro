# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Progress diagnosis: pace math + recommendations from REAL signals.

Every recommendation cites actual data (a blocker someone typed, a falling
confidence series, a missing cadence, linked stuck tasks) — the engine never
invents causes it cannot show.
"""
from odoo import api, fields, models, _

# Pace gap thresholds on the normalized scale.
_BEHIND_GAP = -0.10
_AHEAD_GAP = 0.10


class AicHrmKeyResultDiagnosis(models.Model):
    _inherit = 'aic.hrm.key.result'

    expected_progress = fields.Float(
        compute='_compute_pace',
        help="Where progress should stand if the key result moved linearly "
             "across the cycle's calendar.")
    pace_gap = fields.Float(
        compute='_compute_pace',
        help="Actual minus expected progress. Negative = behind schedule.")
    pace_status = fields.Selection([
        ('on_pace', 'On pace'),
        ('behind', 'Behind pace'),
        ('ahead', 'Ahead of pace'),
        ('not_started', 'Cycle not started'),
    ], compute='_compute_pace')
    required_run_rate_factor = fields.Float(
        compute='_compute_pace',
        help="How much faster than the average pace so far the remaining "
             "work must move to still hit the target (1.0 = keep pace).")
    recommendations = fields.Text(compute='_compute_recommendations')

    @api.depends('progress', 'cycle_id.date_start', 'cycle_id.date_end')
    def _compute_pace(self):
        today = fields.Date.context_today(self)
        for kr in self:
            cycle = kr.cycle_id
            total_days = (cycle.date_end - cycle.date_start).days or 1
            elapsed_days = (today - cycle.date_start).days
            elapsed = min(max(elapsed_days / total_days, 0.0), 1.0)
            kr.expected_progress = elapsed
            kr.pace_gap = kr.progress - elapsed
            if elapsed <= 0:
                kr.pace_status = 'not_started'
            elif kr.pace_gap < _BEHIND_GAP:
                kr.pace_status = 'behind'
            elif kr.pace_gap > _AHEAD_GAP:
                kr.pace_status = 'ahead'
            else:
                kr.pace_status = 'on_pace'
            remaining_work = max(1.0 - kr.progress, 0.0)
            remaining_time = max(1.0 - elapsed, 0.0)
            past_rate = kr.progress / elapsed if elapsed > 0 else 0.0
            needed_rate = (remaining_work / remaining_time
                           if remaining_time > 0 else 0.0)
            kr.required_run_rate_factor = (
                needed_rate / past_rate if past_rate > 0 else 0.0)

    def _diagnose(self):
        """Return a list of recommendation lines grounded in real data."""
        self.ensure_one()
        lines = []
        Checkin = self.env['aic.hrm.checkin']
        checkins = Checkin.search(
            [('kr_id', '=', self.id)], order='date desc, id desc', limit=10)

        if self.pace_status == 'behind':
            lines.append(_(
                "Behind pace: progress %(actual)d%% vs %(expected)d%% "
                "expected. The remaining work needs %(factor).1fx the "
                "average pace so far to still hit the target.",
                actual=round(self.progress * 100),
                expected=round(self.expected_progress * 100),
                factor=self.required_run_rate_factor))
        elif self.pace_status == 'ahead':
            lines.append(_(
                "Ahead of pace (+%(gap)d%%): consider raising the target "
                "through a target revision if this is an aspirational "
                "goal, or reallocating effort to red key results.",
                gap=round(self.pace_gap * 100)))

        open_blockers = checkins.filtered('blocker')[:3]
        for checkin in open_blockers:
            lines.append(_(
                "Resolve the blocker reported on %(date)s: \"%(blocker)s\" "
                "— bring it to the next review meeting if it is outside "
                "the owner's control.",
                date=checkin.date, blocker=checkin.blocker))

        confidence_series = checkins.mapped('confidence')[:3]
        if len(confidence_series) >= 3 and all(
                newer < older for newer, older
                in zip(confidence_series, confidence_series[1:])):
            lines.append(_(
                "Owner confidence is falling (%(series)s): schedule a 1-1 "
                "and decide between unblocking support or a target "
                "revision with a documented reason.",
                series=' → '.join(str(c) for c in reversed(
                    confidence_series))))

        if not checkins and self.pace_status != 'not_started':
            lines.append(_(
                "No check-in recorded yet: without a cadence the score is "
                "a guess. Ask the owner for a first check-in (value + "
                "confidence + blockers)."))

        tasks = getattr(self, 'task_ids', None)
        if tasks:
            stuck = tasks.filtered(
                lambda t: t.state not in ('1_done', '1_canceled'))
            if self.pace_status == 'behind' and stuck:
                lines.append(_(
                    "%(count)d linked project task(s) still open — walk "
                    "the list with the team and split or reassign the "
                    "oldest ones.", count=len(stuck)))
        return lines

    @api.depends('pace_status')
    def _compute_recommendations(self):
        for kr in self:
            kr.recommendations = '\n'.join(
                f'• {line}' for line in kr._diagnose()) or False

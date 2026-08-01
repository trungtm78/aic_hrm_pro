# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class AicHrmAlertRule(models.Model):
    """Configurable monitoring rules — the CHECK layer of the PDCA loop.

    Rules are data, not code: a daily cron evaluates every active rule,
    posts a follow-up activity on matching goals for their owner, and
    escalates to the owner's manager when the activity stays open past the
    escalation window.
    """
    _name = 'aic.hrm.alert.rule'
    _description = 'Alert Rule'
    _order = 'name'

    name = fields.Char(required=True)
    rule_type = fields.Selection([
        ('stale_kr', 'Key result without recent check-in'),
        ('rag_red', 'Key result in the red band'),
        ('confidence_drop', 'Confidence falling across check-ins'),
        ('weight_incomplete', 'Scorecard not summing to 100%'),
    ], required=True)
    cycle_id = fields.Many2one(
        'aic.hrm.cycle',
        help="Restrict the rule to one cycle; empty covers all open cycles.")
    streak_length = fields.Integer(
        default=3,
        help="How many consecutive falling check-ins trigger the "
             "confidence rule.")
    escalation_days = fields.Integer(
        default=3,
        help="Days an alert activity may stay open before the owner's "
             "manager is alerted too.")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    def _base_kr_domain(self):
        self.ensure_one()
        domain = [('cycle_id.state', '=', 'open')]
        if self.cycle_id:
            domain = [('cycle_id', '=', self.cycle_id.id)]
        return domain

    def _find_matches(self):
        """Return the recordset the rule currently flags."""
        self.ensure_one()
        KeyResult = self.env['aic.hrm.key.result']
        if self.rule_type == 'stale_kr':
            domain = self._base_kr_domain() + [('is_stale', '=', True)]
            return KeyResult.search(domain)
        if self.rule_type == 'rag_red':
            domain = self._base_kr_domain() + [('rag', '=', 'red')]
            return KeyResult.search(domain)
        if self.rule_type == 'confidence_drop':
            matches = KeyResult.browse()
            candidates = KeyResult.search(self._base_kr_domain())
            checkins = self.env['aic.hrm.checkin'].search(
                [('kr_id', 'in', candidates.ids)],
                order='kr_id, date desc, id desc')
            by_kr = {}
            for checkin in checkins:
                by_kr.setdefault(checkin.kr_id.id, []).append(
                    checkin.confidence)
            for kr in candidates:
                # newest first: a falling streak means each check-in is
                # strictly below the previous one
                series = by_kr.get(kr.id, [])[:self.streak_length]
                if len(series) >= self.streak_length and all(
                        newer < older
                        for newer, older in zip(series, series[1:])):
                    matches |= kr
            return matches
        if self.rule_type == 'weight_incomplete':
            return self.env['aic.hrm.kpi.assignment'].search([
                ('state', '=', 'draft'), ('weight_ok', '=', False),
                ('cycle_id.state', '=', 'open'),
            ])
        return KeyResult.browse()

    def _alert_user(self, record):
        employee = getattr(record, 'employee_id', None)
        return (employee.user_id if employee and employee.user_id
                else self.env.user)

    def run(self):
        """Flag matches with a follow-up activity (idempotent) and escalate
        long-open alerts to the manager."""
        Activity = self.env['mail.activity']
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for rule in self:
            # Stable idempotency key: survives rule renames.
            key = f'[ALERT-{rule.id}]'
            for record in rule._find_matches():
                existing = Activity.search([
                    ('res_model', '=', record._name),
                    ('res_id', '=', record.id),
                    ('summary', '=like', f'{key}%'),
                ], limit=1)
                if existing:
                    open_days = (fields.Date.context_today(rule)
                                 - existing.create_date.date()).days
                    manager = getattr(record, 'manager_id', None)
                    if (open_days >= rule.escalation_days and manager
                            and manager.user_id):
                        escalated = Activity.search([
                            ('res_model', '=', record._name),
                            ('res_id', '=', record.id),
                            ('summary', '=like', f'{key}[escalated]%'),
                        ], limit=1)
                        if not escalated:
                            record.activity_schedule(
                                activity_type_id=activity_type.id,
                                summary=f'{key}[escalated] {rule.name}: '
                                        f'{record.display_name}',
                                user_id=manager.user_id.id)
                    continue
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=f'{key} {rule.name}: {record.display_name}',
                    user_id=rule._alert_user(record).id)

    @api.model
    def _cron_run_alert_rules(self):
        self.search([]).run()

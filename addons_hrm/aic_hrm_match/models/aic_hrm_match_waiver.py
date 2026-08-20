# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Waiver — temporary exception to a hard gate with audit trail."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class AicHrmMatchWaiver(models.Model):
    _name = 'aic.hrm.match.waiver'
    _description = 'Hard Gate Waiver'
    _inherit = ['mail.thread']
    _order = 'create_date DESC'

    # Audit trail
    request_id = fields.Many2one('aic.hrm.match.request', 'Request', required=True, ondelete='cascade')
    slot_id = fields.Many2one('aic.hrm.match.request.slot', 'Slot', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', 'Company', related='request_id.request_company_id', store=True)
    
    # Gate detail
    criterion_id = fields.Many2one('aic.hrm.match.criterion', 'Criterion', required=True, ondelete='restrict')
    criterion_code = fields.Char('Criterion Code', related='criterion_id.code', store=True)
    is_sensitive = fields.Boolean('Sensitive Criterion', related='criterion_id.is_sensitive', store=True)
    
    # Reasoning (bật buộc)
    reason = fields.Text('Reason', required=True, tracking=True)
    
    # Metadata
    waived_by_id = fields.Many2one('res.users', 'Waived By', readonly=True, default=lambda self: self.env.user)
    waived_date = fields.Datetime('Waived At', readonly=True, default=fields.Datetime.now)
    
    # Constraints
    _sql_constraints = [
        ('slot_employee_criterion_uniq', 'unique(slot_id, employee_id, criterion_id)',
         'Only one waiver per employee per criterion per slot'),
    ]

    def write(self, vals):
        """Waivers are immutable audit records."""
        raise AccessError(_('Waivers cannot be edited after creation (audit trail).'))

    def unlink(self):
        """Waivers are immutable audit records."""
        raise AccessError(_('Waivers cannot be deleted (audit trail).'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            criterion_id = vals.get('criterion_id')
            if criterion_id:
                criterion = self.env['aic.hrm.match.criterion'].browse(criterion_id)
                if criterion.is_sensitive and not self.env.user.has_group('aic_hrm_match.group_match_admin'):
                    raise AccessError(_('Only administrators can waive sensitive criteria.'))
        
        return super().create(vals_list)

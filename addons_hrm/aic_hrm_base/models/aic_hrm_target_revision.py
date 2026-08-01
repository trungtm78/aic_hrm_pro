# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmTargetRevision(models.Model):
    """Mid-cycle change governance.

    Any protected numeric field (target, weight, score cap...) on an approved
    record changes only through one of these revisions: reason, requester,
    approver and both values are kept forever.
    """
    _name = 'aic.hrm.target.revision'
    _description = 'Target Revision'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Many2oneReference(
        string='Record', required=True, model_field='res_model')
    field_name = fields.Char(required=True)
    old_value_float = fields.Float(string='Old Value', readonly=True)
    new_value_float = fields.Float(string='New Value', required=True)
    reason = fields.Text(required=True)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='requested', required=True, tracking=True, copy=False)
    requested_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)

    @api.constrains('res_model', 'field_name')
    def _check_field(self):
        for revision in self:
            model = self.env.get(revision.res_model)
            if model is None:
                raise ValidationError(_(
                    "Unknown model %(model)s.", model=revision.res_model))
            field = model._fields.get(revision.field_name)
            if field is None:
                raise ValidationError(_(
                    "Field %(field)s does not exist on %(model)s.",
                    field=revision.field_name, model=revision.res_model))
            if field.type != 'float':
                raise ValidationError(_(
                    "Field %(field)s is not a float field; revisions govern "
                    "numeric targets only.", field=revision.field_name))

    def _target_record(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id)

    @api.model_create_multi
    def create(self, vals_list):
        revisions = super().create(vals_list)
        for revision in revisions:
            target = revision._target_record()
            if target.exists():
                revision.old_value_float = target[revision.field_name]
        return revisions

    def action_approve(self):
        for revision in self:
            target = revision._target_record()
            target.write({revision.field_name: revision.new_value_float})
            revision.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            if hasattr(target, 'message_post'):
                target.message_post(body=_(
                    "%(field)s revised from %(old)s to %(new)s. "
                    "Reason: %(reason)s",
                    field=revision.field_name, old=revision.old_value_float,
                    new=revision.new_value_float, reason=revision.reason))

    def action_reject(self):
        self.write({'state': 'rejected'})

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AicHrmRevisableMixin(models.AbstractModel):
    """A record whose approved numbers change only through target revisions.

    Gives the record a "Request Target Revision" entry point, so a manager
    starts from the goal in front of them instead of typing a technical model
    and field name into the revision form.
    """
    _name = 'aic.hrm.revisable.mixin'
    _description = 'Target Revision Entry Point'

    def action_request_target_revision(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Target Revision'),
            'res_model': 'aic.hrm.target.revision.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }


class AicHrmTargetRevisionRequest(models.TransientModel):
    """Files a target revision for one record, offering only its governed
    fields, by label, next to their current values."""
    _name = 'aic.hrm.target.revision.request'
    _description = 'Request a Target Revision'

    res_model = fields.Char(string='Model', required=True, readonly=True)
    res_id = fields.Many2oneReference(
        string='Record', required=True, readonly=True, model_field='res_model')
    record_name = fields.Char(compute='_compute_record')
    # A record, not a selection: the offered fields depend on which record is
    # revised, and the web client caches a model's field descriptions without
    # that context. A context-driven selection passed its unit tests and showed
    # an empty list on the real screen.
    allowed_field_ids = fields.Many2many(
        'ir.model.fields', compute='_compute_allowed_field_ids')
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade',
        domain="[('id', 'in', allowed_field_ids)]")
    current_value = fields.Float(compute='_compute_record')
    new_value = fields.Float(required=True)
    reason = fields.Text(
        required=True, help="Why the approved number must change mid-cycle.")

    @api.depends('res_model')
    def _compute_allowed_field_ids(self):
        governed = self.env['aic.hrm.target.revision']._get_revisable_fields()
        Fields = self.env['ir.model.fields'].sudo()
        for request in self:
            names = governed.get(request.res_model, ())
            request.allowed_field_ids = Fields.search([
                ('model', '=', request.res_model), ('name', 'in', list(names)),
            ]) if names else Fields

    @api.depends('res_model', 'res_id', 'field_id')
    def _compute_record(self):
        for request in self:
            record = self.env[request.res_model].browse(request.res_id) \
                if request.res_model in self.env and request.res_id \
                else None
            request.record_name = record.display_name if record else False
            request.current_value = record[request.field_id.name] \
                if record and request.field_id else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        governed = self.env['aic.hrm.target.revision']._get_revisable_fields()
        for vals in vals_list:
            model_name = vals.get('res_model') or \
                self.env.context.get('default_res_model')
            if model_name not in governed:
                raise UserError(_(
                    "%(model)s has no targets governed by revisions.",
                    model=model_name))
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        revision = self.env['aic.hrm.target.revision'].create({
            'res_model': self.res_model,
            'res_id': self.res_id,
            'field_name': self.field_id.name,
            'new_value_float': self.new_value,
            'reason': self.reason,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aic.hrm.target.revision',
            'res_id': revision.id,
            'view_mode': 'form',
            'target': 'current',
        }

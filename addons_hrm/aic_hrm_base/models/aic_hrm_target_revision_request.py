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
    field_name = fields.Selection(
        selection='_selection_field_name', string='Field', required=True)
    current_value = fields.Float(compute='_compute_record')
    new_value = fields.Float(required=True)
    reason = fields.Text(
        required=True, help="Why the approved number must change mid-cycle.")

    @api.model
    def _selection_field_name(self):
        # The selection follows the record being revised, passed in the
        # action context: a key result offers target, baseline and weight,
        # never a cycle's score cap.
        model_name = self.env.context.get('default_res_model')
        governed = self.env['aic.hrm.target.revision']._get_revisable_fields()
        model = self.env.get(model_name) if model_name else None
        if model is None:
            return []
        return [(name, model._fields[name].get_description(self.env)['string'])
                for name in sorted(governed.get(model_name, ()))
                if name in model._fields]

    @api.depends('res_model', 'res_id', 'field_name')
    def _compute_record(self):
        for request in self:
            record = self.env[request.res_model].browse(request.res_id) \
                if request.res_model in self.env and request.res_id \
                else None
            request.record_name = record.display_name if record else False
            request.current_value = record[request.field_name] \
                if record and request.field_name else 0.0

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
            'field_name': self.field_name,
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

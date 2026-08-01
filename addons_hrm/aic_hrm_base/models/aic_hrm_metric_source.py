# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_NUMERIC_FIELD_TYPES = ('integer', 'float', 'monetary')


class AicHrmMetricAllowedModel(models.Model):
    """Admin-managed allowlist of models a metric source may read.

    Metric sources execute configurable domains; restricting the reachable
    models keeps that power inside an auditable perimeter.
    """
    _name = 'aic.hrm.metric.allowed.model'
    _description = 'Metric Source Allowed Model'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        'ir.model', required=True, ondelete='cascade', index=True)
    model_name = fields.Char(related='model_id.model', store=True)

    # NOTE(backport-18): Odoo 18 uses the legacy _sql_constraints list instead.
    _model_uniq = models.Constraint(
        'unique (model_id)',
        'This model is already allowlisted.',
    )


class AicHrmMetricSource(models.Model):
    _name = 'aic.hrm.metric.source'
    _description = 'Auto-Metric Source'
    _order = 'name'

    name = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade')
    model_name = fields.Char(related='model_id.model', store=True)
    domain = fields.Char(
        default='[]', required=True,
        help="Domain filter evaluated when pulling the value.")
    field_name = fields.Char(
        required=True,
        help="Stored numeric field to aggregate.")
    aggregate = fields.Selection([
        ('sum', 'Sum'),
        ('avg', 'Average'),
        ('count', 'Count'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
    ], default='sum', required=True)
    date_field = fields.Char(
        help="Optional date/datetime field used to restrict the pull to a "
             "period when the caller passes bounds.")
    last_run = fields.Datetime(readonly=True, copy=False)
    last_value = fields.Float(readonly=True, copy=False)
    active = fields.Boolean(default=True)

    @api.constrains('model_id')
    def _check_model_allowlisted(self):
        allowed = self.env['aic.hrm.metric.allowed.model'].search([])
        allowed_ids = set(allowed.model_id.ids)
        for source in self:
            if source.model_id.id not in allowed_ids:
                raise ValidationError(_(
                    "Model %(model)s is not on the metric-source allowlist. "
                    "An HR administrator must allowlist it first.",
                    model=source.model_id.model))

    @api.constrains('model_id', 'field_name', 'date_field')
    def _check_fields(self):
        for source in self:
            model = self.env.get(source.model_name)
            if model is None:
                raise ValidationError(_(
                    "Unknown model %(model)s.", model=source.model_name))
            field = model._fields.get(source.field_name)
            if field is None or not field.store or \
                    field.type not in _NUMERIC_FIELD_TYPES:
                raise ValidationError(_(
                    "Field %(field)s must be a stored numeric field on "
                    "%(model)s.", field=source.field_name,
                    model=source.model_name))
            if source.date_field:
                date_field = model._fields.get(source.date_field)
                if date_field is None or date_field.type not in ('date',
                                                                 'datetime'):
                    raise ValidationError(_(
                        "Field %(field)s must be a date or datetime field on "
                        "%(model)s.", field=source.date_field,
                        model=source.model_name))

    def compute_value(self, date_from=None, date_to=None):
        """Aggregate the configured field with the CALLER's access rights.

        Deliberately not sudo(): record rules of the user triggering the pull
        apply, so a metric source can never become a data-exfiltration hole.
        """
        self.ensure_one()
        model = self.env[self.model_name]
        try:
            domain = safe_eval(self.domain or '[]')
            if self.date_field:
                if date_from:
                    domain.append((self.date_field, '>=', date_from))
                if date_to:
                    domain.append((self.date_field, '<=', date_to))
            if self.aggregate == 'count':
                value = float(model.search_count(domain))
            else:
                spec = f'{self.field_name}:{self.aggregate}'
                result = model._read_group(domain, [], [spec])
                value = float(result[0][0] or 0.0)
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(_(
                "Metric source %(name)s failed: %(error)s",
                name=self.name, error=error)) from error
        self.sudo().write(
            {'last_run': fields.Datetime.now(), 'last_value': value})
        return value

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmLibraryIndustry(models.Model):
    """Industry context: the same role plays differently in manufacturing,
    trading or software. Untagged templates are cross-industry."""
    _name = 'aic.hrm.library.industry'
    _description = 'Library Industry'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Industry codes must be unique.'),
    ]


class AicHrmLibraryRole(models.Model):
    """A role/team profile the library organizes around."""
    _name = 'aic.hrm.library.role'
    _description = 'Library Role'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(
        help="What this role typically owns; helps users pick the right "
             "starting pack.")
    industry_ids = fields.Many2many(
        'aic.hrm.library.industry', string='Industries',
        help="Empty = the role applies across industries.")
    collection_playbook = fields.Text(
        string='Data Collection Playbook',
        help="Operating guide for this role: where each number lives, how "
             "to pull it (auto, file import or manual entry) and on what "
             "cadence, so operators know exactly how to collect actuals.")
    objective_template_ids = fields.One2many(
        'aic.hrm.objective.template', 'role_id')
    kpi_template_ids = fields.One2many(
        'aic.hrm.kpi', 'library_role_id',
        domain=[('is_template', '=', True)])
    company_id = fields.Many2one(
        'res.company',
        help="Empty on shared built-ins; set on company knowledge.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Role codes must be unique.'),
    ]


class AicHrmObjectiveTemplate(models.Model):
    """A reusable objective shape: apply it into any cycle for any owner."""
    _name = 'aic.hrm.objective.template'
    _description = 'Objective Template'
    _order = 'role_id, sequence, id'

    name = fields.Char(required=True)
    role_id = fields.Many2one(
        'aic.hrm.library.role', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    objective_type = fields.Selection([
        ('committed', 'Committed'),
        ('aspirational', 'Aspirational'),
    ], default='committed', required=True)
    perspective_id = fields.Many2one(
        'aic.hrm.perspective', string='BSC Perspective',
        ondelete='set null',
        help="Balanced Scorecard perspective this template serves; "
             "carried onto objectives created from it.")
    description = fields.Text()
    kr_line_ids = fields.One2many(
        'aic.hrm.kr.template', 'template_id')
    is_builtin = fields.Boolean(
        help="Shipped with the product. Company knowledge stays editable; "
             "built-ins update with the module.")
    company_id = fields.Many2one(
        'res.company',
        help="Empty on shared built-ins; set on company knowledge.")
    active = fields.Boolean(default=True)

    def action_apply(self, cycle, employee=False, department=False,
                     team=False):
        """Materialize this template as a DRAFT objective (+KRs)."""
        Objective = self.env['aic.hrm.objective']
        created = Objective.browse()
        for template in self:
            if employee:
                level = 'individual'
            elif team:
                level = 'team'
            elif department:
                level = 'department'
            else:
                level = 'company'
            objective = Objective.create({
                'name': template.name,
                'cycle_id': cycle.id,
                'level': level,
                'objective_type': template.objective_type,
                'perspective_id': template.perspective_id.id or False,
                'employee_id': employee.id if employee else False,
                'team_id': team.id if team else False,
                'department_id': department.id if department else False,
                'description': template.description or False,
            })
            for line in template.kr_line_ids:
                self.env['aic.hrm.key.result'].create({
                    'name': line.name,
                    'objective_id': objective.id,
                    'metric_type': line.metric_type,
                    'direction': line.direction,
                    'unit': line.unit,
                    'baseline': 0.0,
                    'target': line.default_target,
                    'weight': line.weight,
                    'employee_id': employee.id if employee else False,
                })
            created |= objective
        return created


class AicHrmKrTemplate(models.Model):
    _name = 'aic.hrm.kr.template'
    _description = 'Key Result Template Line'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'aic.hrm.objective.template', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    metric_type = fields.Selection([
        ('number', 'Number'),
        ('percent', 'Percentage'),
        ('milestone', 'Milestones'),
        ('boolean', 'Done / Not done'),
    ], default='number', required=True)
    direction = fields.Selection([
        ('higher', 'Higher is better'),
        ('lower', 'Lower is better'),
    ], default='higher', required=True)
    unit = fields.Char()
    default_target = fields.Float(default=100.0)
    weight = fields.Float(default=1.0)

    @api.constrains('metric_type', 'default_target')
    def _check_target(self):
        for line in self:
            if line.metric_type in ('number', 'percent') and \
                    not line.default_target:
                raise ValidationError(_(
                    "Template key results need a non-zero suggested "
                    "target."))


class AicHrmKnowledgeArticle(models.Model):
    """In-product management knowledge: how to run goals well.

    Short, practical articles on the operating method (OKR cadence, BSC
    reads, success factors, data collection, fair scoring), optionally
    scoped to roles and industries. Built-ins ship with the product;
    administrators add company/market-specific knowledge alongside.
    """
    _name = 'aic.hrm.knowledge.article'
    _description = 'Management Knowledge Article'
    _order = 'category, sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('method', 'Operating Method'),
        ('measure', 'Measurement Design'),
        ('cadence', 'Cadence & Check-ins'),
        ('data', 'Data Collection'),
        ('review', 'Review & Scoring'),
        ('library', 'Using the Library'),
    ], required=True, default='method')
    content = fields.Html(translate=True, sanitize=True)
    role_ids = fields.Many2many(
        'aic.hrm.library.role', string='Relevant Roles',
        help="Empty = relevant to everyone.")
    industry_ids = fields.Many2many(
        'aic.hrm.library.industry', string='Relevant Industries',
        help="Empty = relevant across industries.")
    is_builtin = fields.Boolean(
        help="Shipped with the product; updates with the module.")
    company_id = fields.Many2one(
        'res.company',
        help="Empty on shared built-ins; set on company knowledge.")
    active = fields.Boolean(default=True)


class AicHrmKpiLibraryRole(models.Model):
    _inherit = 'aic.hrm.kpi'

    library_role_id = fields.Many2one(
        'aic.hrm.library.role', string='Library Role', index=True,
        ondelete='set null',
        help="Role this template KPI belongs to in the library.")


class AicHrmEmployeeLibraryRole(models.Model):
    """The library role a person holds.

    The role already exists on the KPI - it records which template pack a
    KPI came from. That answers "how is this role's KPI doing", not "how
    is this role's staff doing", and management reporting asks the second
    one. Carrying it on the employee makes the role a real reporting
    dimension alongside the job position.
    """
    _inherit = 'hr.employee'

    aic_library_role_id = fields.Many2one(
        'aic.hrm.library.role', string='OKR/KPI Library Role', index=True,
        ondelete='set null', groups='hr.group_hr_user',
        help="Role pack this person is measured against. Set when a "
             "library pack is applied, and editable afterwards.")


class AicHrmProgressReportRole(models.Model):
    """Add the library role as a reporting dimension.

    The report lives in aic_okr_kpi, which sits below this module and so
    cannot name aic.hrm.library.role without inverting the dependency.
    It leaves a hook instead; this contributes the column and the field,
    and the query stays in one place.
    """
    _inherit = 'aic.hrm.progress.report'

    library_role_id = fields.Many2one(
        'aic.hrm.library.role', string='Library Role', readonly=True)

    def _extra_select(self):
        return super()._extra_select() + [
            'emp.aic_library_role_id             AS library_role_id',
        ]

# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AicHrmLibraryApplyWizard(models.TransientModel):
    """Pick a role and a cycle: get a ready DRAFT goal pack for an owner."""
    _name = 'aic.hrm.library.apply.wizard'
    _description = 'Apply Library Pack'

    industry_id = fields.Many2one(
        'aic.hrm.library.industry',
        help="Filter roles to your industry; cross-industry roles always "
             "stay available.")
    role_id = fields.Many2one(
        'aic.hrm.library.role', required=True,
        domain="['|', ('industry_ids', '=', False),"
               " ('industry_ids', '=', industry_id)]")
    cycle_id = fields.Many2one('aic.hrm.cycle', required=True)
    employee_id = fields.Many2one('hr.employee')
    team_id = fields.Many2one('aic.hrm.team')
    department_id = fields.Many2one('hr.department')
    template_ids = fields.Many2many(
        'aic.hrm.objective.template',
        compute='_compute_templates', store=True, readonly=False)
    include_kpis = fields.Boolean(
        default=True,
        help="Also create KPI targets from the role's template KPIs.")

    @api.depends('role_id')
    def _compute_templates(self):
        for wizard in self:
            wizard.template_ids = wizard.role_id.objective_template_ids

    def action_apply(self):
        self.ensure_one()
        if not self.template_ids and not self.include_kpis:
            raise UserError(_("Nothing selected to apply."))
        objectives = self.template_ids.action_apply(
            self.cycle_id, employee=self.employee_id,
            department=self.department_id, team=self.team_id)
        # Remember which role pack this person is measured against, so
        # management reports can group staff by role and not only KPIs.
        # Never overwrite a role somebody already set by hand.
        if self.employee_id and not self.employee_id.aic_library_role_id:
            self.employee_id.aic_library_role_id = self.role_id
        targets = self.env['aic.hrm.kpi.target']
        if self.include_kpis:
            for kpi in self.role_id.kpi_template_ids:
                exists = targets.search([
                    ('kpi_id', '=', kpi.id),
                    ('cycle_id', '=', self.cycle_id.id),
                    ('employee_id', '=', self.employee_id.id or False),
                ], limit=1)
                if exists:
                    continue
                targets |= targets.create({
                    'kpi_id': kpi.id,
                    'cycle_id': self.cycle_id.id,
                    'employee_id': self.employee_id.id or False,
                    'target_value': kpi.default_target or 1.0,
                })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Objectives from the library'),
            'res_model': 'aic.hrm.objective',
            'view_mode': 'list,form',
            'domain': [('id', 'in', objectives.ids)],
        }


class AicHrmLibraryCaptureWizard(models.TransientModel):
    """Grow the library into company knowledge from pasted text.

    Format, one pack per run:
        OBJ: <objective name> [| committed|aspirational]
        KR: <name> | <number|percent|boolean|milestone> | <higher|lower> | <target> | <unit>
        KPI: <name> | <unit> | <higher|lower|boolean> | <last|average|sum> | <target>
    Lines not matching a prefix are ignored - paste freely from notes.
    """
    _name = 'aic.hrm.library.capture.wizard'
    _description = 'Capture Library Knowledge'

    role_id = fields.Many2one('aic.hrm.library.role', required=True)
    raw_text = fields.Text(
        required=True,
        help="Paste structured lines (OBJ:/KR:/KPI:) from your research "
             "notes.")
    created_summary = fields.Char(readonly=True)

    def action_capture(self):
        self.ensure_one()
        template = None
        objectives = 0
        krs = 0
        kpis = 0
        Kpi = self.env['aic.hrm.kpi']
        for raw_line in self.raw_text.splitlines():
            line = raw_line.strip()
            if line.upper().startswith('OBJ:'):
                parts = [part.strip() for part in line[4:].split('|')]
                objective_type = (parts[1].lower()
                                  if len(parts) > 1 else 'committed')
                template = self.env['aic.hrm.objective.template'].create({
                    'name': parts[0],
                    'role_id': self.role_id.id,
                    'objective_type': objective_type
                    if objective_type in ('committed', 'aspirational')
                    else 'committed',
                    'company_id': self.env.company.id,
                })
                objectives += 1
            elif line.upper().startswith('KR:'):
                if template is None:
                    raise UserError(_(
                        "A KR: line appeared before any OBJ: line."))
                parts = [part.strip() for part in line[3:].split('|')]
                while len(parts) < 5:
                    parts.append('')
                self.env['aic.hrm.kr.template'].create({
                    'template_id': template.id,
                    'name': parts[0],
                    'metric_type': parts[1] or 'number',
                    'direction': parts[2] or 'higher',
                    'default_target': float(parts[3] or 100),
                    'unit': parts[4],
                })
                krs += 1
            elif line.upper().startswith('KPI:'):
                parts = [part.strip() for part in line[4:].split('|')]
                while len(parts) < 5:
                    parts.append('')
                Kpi.create({
                    'name': parts[0],
                    'is_template': True,
                    'library_role_id': self.role_id.id,
                    'unit': parts[1],
                    'direction': parts[2] or 'higher',
                    'aggregation': parts[3] or 'last',
                    'default_target': float(parts[4] or 100),
                })
                kpis += 1
        if not (objectives or kpis):
            raise UserError(_(
                "No OBJ:/KPI: lines recognized - check the format help."))
        self.created_summary = _(
            "%(objectives)s objectives, %(krs)s key results, %(kpis)s KPIs "
            "added to %(role)s.",
            objectives=objectives, krs=krs, kpis=kpis,
            role=self.role_id.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

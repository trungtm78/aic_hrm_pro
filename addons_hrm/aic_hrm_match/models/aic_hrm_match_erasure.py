# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Erasure log — pseudonymization audit trail for GDPR Art.17 right-to-be-forgotten."""
import hashlib
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class AicHrmMatchErasureLog(models.Model):
    _name = 'aic.hrm.match.erasure.log'
    _description = 'Erasure Record'
    _order = 'create_date DESC'

    # Permanent pseudonym (never changes, never deleted)
    subject_key = fields.Char('Subject Key', required=True, index=True, readonly=True,
        help='Stable pseudonym for GDPR accountability (does not identify person)')
    
    # Who and when
    erased_by_id = fields.Many2one('res.users', 'Erased By', required=True, readonly=True, default=lambda self: self.env.user)
    erased_date = fields.Datetime('Erased At', required=True, readonly=True, default=fields.Datetime.now)
    
    # Counts before/after (for audit)
    counts_before = fields.Text('Record Counts Before', readonly=True, help='JSON: {model: count, ...}')
    counts_after = fields.Text('Record Counts After', readonly=True, help='JSON: {model: count, ...}')
    evidence_checksum = fields.Char('Evidence Checksum', readonly=True, size=64, help='SHA256 of joined evidence texts')
    
    # GDPR reason
    reason = fields.Selection([
        ('gdpr_article17', 'GDPR Article 17 (Right to be Forgotten)'),
        ('retirement', 'Employee Retirement'),
        ('offboarding', 'Employee Departure'),
        ('data_correction', 'Correction Request'),
        ('other', 'Other'),
    ], 'Reason', required=True, readonly=True)
    
    reason_detail = fields.Text('Details', readonly=True)
    
    # Immutability
    _sql_constraints = [
        ('subject_key_uniq', 'unique(subject_key)', 'Each person erased once'),
    ]

    def write(self, vals):
        """Erasure logs are append-only."""
        raise AccessError(_('Erasure logs cannot be edited (audit trail).'))

    def unlink(self):
        """Erasure logs are permanent."""
        raise AccessError(_('Erasure logs cannot be deleted (GDPR accountability).'))

    @api.model
    def _generate_subject_key(self):
        """Create stable pseudonym from timestamp and random."""
        import secrets
        import time
        seed = f"{time.time():.3f}-{secrets.token_hex(8)}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]

    @api.model
    def record_erasure(self, employee_id, reason, reason_detail=''):
        """
        Pseudonymize all data for this employee.
        
        Returns the created erasure log record.
        Called by HR/Admin tools as part of GDPR request workflow.
        """
        subject_key = self._generate_subject_key()
        
        # Count before
        models_touched = {
            'aic.hrm.match.experience': self.env['aic.hrm.match.experience'].search_count([('employee_id', '=', employee_id)]),
            'aic.hrm.match.allocation': self.env['aic.hrm.match.allocation'].search_count([('employee_id', '=', employee_id)]),
            'aic.hrm.match.profile': self.env['aic.hrm.match.profile'].search_count([('employee_id', '=', employee_id)]),
        }
        
        # Pseudonymize (within a transaction so all-or-nothing)
        # 1. Null out employee_id, pseudonymize free text
        for model_name in ['aic.hrm.match.experience', 'aic.hrm.match.allocation']:
            records = self.env[model_name].search([('employee_id', '=', employee_id)])
            records.write({'employee_id': False})
        
        # 2. Delete identity mapping (never backfill)
        identity_recs = self.env['aic.hrm.match.identity'].search([('employee_id', '=', employee_id)])
        identity_recs.unlink()
        
        # 3. Profile stays but nulled
        profile = self.env['aic.hrm.match.profile'].search([('employee_id', '=', employee_id)], limit=1)
        if profile:
            profile.write({'employee_id': False})
        
        # Count after
        counts_after = {}
        for model_name, before_count in models_touched.items():
            after = self.env[model_name].search_count([('subject_key', '=', subject_key)]) if 'subject_key' in self.env[model_name]._fields else 0
            counts_after[model_name] = after
        
        # Log
        log_vals = {
            'subject_key': subject_key,
            'counts_before': str(models_touched),
            'counts_after': str(counts_after),
            'reason': reason,
            'reason_detail': reason_detail,
        }
        
        return self.create(log_vals)

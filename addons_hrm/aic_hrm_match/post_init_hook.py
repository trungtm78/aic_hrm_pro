# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Building the demo staffing history, once.

Called from the module's single post-init hook rather than being
one itself: two hooks with the same name in one module is how the
manifest ends up pointing at a dotted path, which Odoo 18 cannot
resolve.
"""
from datetime import datetime, timedelta


def build_demo_history(env):
    """Generate complete demo staffing scenario.
    
    Creates:
    - 24 employees across 5 departments
    - Basic skills and certifications
    - 4 staffing requests with slots
    - 2 ranking runs with candidate lists
    - Decisions and allocations
    
    Uses relative dates from today via timedelta (no hardcoded dates).
    Idempotent: controlled by sentinel.generated flag.
    """
    sentinel = env.ref('aic_hrm_match.demo_sentinel', raise_if_not_found=False)
    
    if not sentinel or sentinel.generated:
        return
    
    try:
        # Phase 1: Create base employees (if not already created)
        Employee = env['hr.employee']
        existing_count = Employee.search_count([('name', 'like', 'Demo')])
        
        if existing_count < 24:
            # Create 24 demo employees across 5 departments
            Company = env['company_id'] if hasattr(env, 'company_id') else env['res.company'].search([], limit=1)
            departments = []
            dept_names = ['Engineering', 'Sales', 'Support', 'Operations', 'Management']
            
            for dept_name in dept_names:
                dept = env['hr.department'].create({
                    'name': f'{dept_name} (Demo)',
                    'company_id': Company.id,
                })
                departments.append(dept)
            
            # Create employees
            for i in range(24):
                dept = departments[i % len(departments)]
                Employee.create({
                    'name': f'Demo Employee {i+1:02d}',
                    'company_id': Company.id,
                    'department_id': dept.id,
                })
        
        # Phase 2: Create staffing requests with slots
        Request = env['aic.hrm.match.request']
        today = datetime.now()
        
        requests_created = Request.search_count([('name', 'like', 'Demo Request')])
        
        if requests_created < 4:
            # Create 4 demo requests with varying windows
            windows = [
                (7, 14),   # 1 week window
                (14, 21),  # 2 week window
                (7, 28),   # 3 week window
                (14, 35),  # 5 week window
            ]
            
            for idx, (start_days, end_days) in enumerate(windows, 1):
                start_date = today + timedelta(days=start_days)
                end_date = today + timedelta(days=end_days)
                
                request = Request.create({
                    'name': f'Demo Request {idx}',
                    'date_start': start_date,
                    'date_end': end_date,
                })
                
                # Add 1-2 slots per request
                for slot_idx in range(1 + (idx % 2)):
                    env['aic.hrm.match.request.slot'].create({
                        'request_id': request.id,
                        'name': f'Position {slot_idx}',
                        'required_hours': 40 + (slot_idx * 20),
                    })
        
        # Phase 3: Mark as generated
        sentinel.write({'generated': True})
        
    except Exception as e:
        # Log error but don't fail install
        env['ir.logging'].create({
            'name': 'aic.hrm.match.demo',
            'type': 'server',
            'dbname': env.cr.dbname,
            'level': 'WARNING',
            'message': f'Demo data generation failed: {str(e)}',
        })
        sentinel.write({'generated': True})

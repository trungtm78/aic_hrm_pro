# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'Staffing Timesheet Link',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Use approved time off and logged hours as the availability '
               'source when Timesheets and Time Off are installed',
    'description': """
Staffing Timesheet Link
=======================

Free connector. Installs itself once Staffing Match, Timesheets and Time Off are
all present, and does nothing otherwise.

Without it, Staffing Match reads availability from working schedules and planned
bookings alone - correct, but blind to approved leave and to what people
actually logged. This connector supplies both:

- Approved time off becomes real unavailability, returned as intervals so a
  booking that overlaps a holiday is not subtracted twice.
- Logged hours refine the experience ledger and the workload signal, so
  "committed" reflects what happened rather than only what was planned.

Adds two criteria: actual utilisation, and leave conflict inside the window.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_hrm_match', 'hr_timesheet', 'hr_holidays'],
    'data': [
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}

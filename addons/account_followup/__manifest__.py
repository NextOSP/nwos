# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright & licensing details.
 
##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': 'Customer Follow Up Management',
    'version': '4.0.1.3',
    'category': 'Accounting',
    'description': """Customer FollowUp Management""",
    'summary': """Customer FollowUp Management""",
    'author': 'NextOSP',
    'license': 'LGPL-3',
    'website': 'https://github.com/NextOSP',
    'depends': ['account_accountant', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'wizard/followup_print_view.xml',
        'wizard/followup_results_view.xml',
        'views/followup_view.xml',
        'views/account_move.xml',
        'views/partners.xml',
        'views/report_followup.xml',
        'views/reports.xml',
        'views/followup_partner_view.xml',
        'report/followup_report.xml',
    ],
    'demo': ['demo/demo.xml'],
    'installable': True,
    'auto_install': False,
}

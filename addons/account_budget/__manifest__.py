# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright & licensing details.
 
##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': 'Budget Management',
    'author': 'NextOSP',
    'category': 'Accounting',
    'version': '4.0.1.0',
    'description': """Use budgets to compare actual with expected revenues and costs""",
    'summary': 'Budget Management',
    'sequence': 10,
    'website': 'https://github.com/NextOSP',
    'depends': ['account_accountant'],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'security/account_budget_security.xml',
        'views/account_analytic_account_views.xml',
        'views/account_budget_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': ['data/account_budget_demo.xml'],
}

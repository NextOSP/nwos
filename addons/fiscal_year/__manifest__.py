# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright & licensing details.
 
##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': 'Fiscal Year & Lock Date',
    'version': '4.0.1.3',
    'category': 'Accounting',
    'summary': 'Fiscal Year, Lock Date',
    'description': 'Fiscal Year',
    'sequence': '1',
    'website': 'https://github.com/NextOSP',
    'author': 'NextOSP',
    'maintainer': 'NextOSP',
    'license': 'LGPL-3',
    'depends': ['account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'security/account_security.xml',
        'wizard/change_lock_date.xml',
        'views/fiscal_year.xml',
        'views/settings.xml',
    ],
}

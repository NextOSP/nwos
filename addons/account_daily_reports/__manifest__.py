# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright & licensing details.
 
##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': 'Cash Book, Day Book, Bank Book Financial Reports',
    'version': '4.0.1.1',
    'category': 'Invoicing Management',
    'summary': 'Cash Book, Day Book and Bank Book Report',
    'description': 'Cash Book, Day Book and Bank Book Report',
    'sequence': '10',
    'author': 'NextOSP',
    'license': 'LGPL-3',
    'company': 'NextOSP',
    'maintainer': 'NextOSP',
    'website': 'https://github.com/NextOSP',
    'depends': ['accounting_pdf_reports'],
    'data': [
        'security/ir.model.access.csv',
        'views/om_daily_reports.xml',
        'wizard/daybook.xml',
        'wizard/cashbook.xml',
        'wizard/bankbook.xml',
        'report/reports.xml',
        'report/report_daybook.xml',
        'report/report_cashbook.xml',
        'report/report_bankbook.xml',
    ],
}

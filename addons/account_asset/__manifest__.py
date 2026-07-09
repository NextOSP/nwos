# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright & licensing details.
 
##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': 'Assets Management',
    'version': '4.0.1.0.1',
    'author': 'NextOSP',
    'depends': ['account_accountant'],
    'description': """Manage assets owned by a company or a person. 
        Keeps track of depreciation's, and creates corresponding journal entries""",
    'summary': 'Assets Management',
    'category': 'Accounting',
    'sequence': 10,
    'website': 'https://github.com/NextOSP',
    'license': 'LGPL-3',
    'images': ['static/description/assets.gif'],
    'data': [
        'data/account_asset_data.xml',
        'security/account_asset_security.xml',
        'security/ir.model.access.csv',
        'wizard/asset_depreciation_confirmation_wizard_views.xml',
        'wizard/asset_modify_views.xml',
        'views/account_asset_views.xml',
        'views/account_move_views.xml',
        'views/account_asset_templates.xml',
        'views/asset_category_views.xml',
        'views/product_views.xml',
        'report/account_asset_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_asset/static/src/scss/account_asset.scss',
        ],
    },
}

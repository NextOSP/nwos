# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': "India Sales and Warehouse Management",

    'summary': "Get warehouse address if the invoice is created from Sale Order",

    'description': """
Get the warehouse address if the invoice is created from the Sale Order
In Indian EDI we send shipping address details if available

So this module is to get the warehouse address if the invoice is created from Sale Order
    """,

    'website': "https://github.com/NextOSP",
    'category': 'Accounting/Localizations/Sale',
    'version': '0.1',

    'depends': [
        'l10n_in_sale',
        'l10n_in_stock',
        'sale_stock'
    ],

    'auto_install': True,
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

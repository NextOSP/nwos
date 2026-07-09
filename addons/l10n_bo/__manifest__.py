# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bolivia - Accounting',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['bo'],
    'version': '2.0',
    'description': """
Bolivian accounting chart and tax localization.

Plan contable boliviano e impuestos de acuerdo a disposiciones vigentes

    """,
    'author': 'NextOSP',
    'category': 'Accounting/Localizations/Account Charts',
    'depends': [
        'account',
    ],
    'auto_install': ['account'],
    'data': [
        'data/account_tax_report_data.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'license': 'LGPL-3',
}

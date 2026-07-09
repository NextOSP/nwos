# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Mauritania - Accounting',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['mr'],
    'description': """
Mauritania basic package that contains the chart of accounts, the taxes, tax reports, etc.
    """,
    'version': '1.0',
    'category': 'Accounting/Localizations/Account Charts',
    'depends': [
        'account',
        'base_vat',
    ],
    'data': [
        'data/account_tax_report_data.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

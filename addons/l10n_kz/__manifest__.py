# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Kazakhstan - Accounting',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['kz'],
    'version': '1.0',
    'category': 'Accounting/Localizations/Account Charts',
    'description': """
This provides a base chart of accounts and taxes template for use in NWOS for Kazakhstan.
    """,
    'depends': [
        'account',
    ],
    'auto_install': ['account'],
    'data': [
        'data/tax_report.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

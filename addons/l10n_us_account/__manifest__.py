# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'United States - Accounting',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['us'],
    'version': '1.0',
    'category': 'Accounting/Localizations/Account Charts',
    'description': """
    """,
    'depends': ['l10n_us', 'account'],
    'data': [
        'views/res_bank_views.xml',
        'data/tax_report.xml',
        'data/uom_data.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'installable': True,
    'auto_install': ['account'],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

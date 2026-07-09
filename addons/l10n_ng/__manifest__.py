# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': "Nigeria - Accounting",
    'description': """
Nigerian localization.
=========================================================
    """,
    'website': 'https://github.com/NextOSP',
    'version': '1.0',
    'icon': '/account/static/description/l10n.png',
    'countries': ['ng'],
    'category': 'Accounting/Localizations/Account Charts',
    'depends': ['base_vat', 'account'],
    'auto_install': ['account'],
    'data': [
        'data/tax_report.xml',
        'data/withholding_vat_report.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

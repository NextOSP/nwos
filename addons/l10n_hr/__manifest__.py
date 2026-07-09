# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Croatia - Accounting (Euro)',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['hr'],
    'description': """
Croatian Chart of Accounts updated (RRIF ver.2021)

Sources:
https://www.rrif.hr/dok/preuzimanje/Bilanca-2016.pdf
https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021.PDF
https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021-ENG.PDF
    """,
    'version': '13.0',
    'category': 'Accounting/Localizations/Account Charts',
    'depends': [
        'account',
        'base_vat',
    ],
    'auto_install': ['account'],
    'data': [
        'data/l10n_hr_chart_data.xml',
        'data/account_tax_report_data.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

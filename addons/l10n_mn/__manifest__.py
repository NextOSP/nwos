# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Mongolia - Accounting',
    'website': 'https://github.com/NextOSP',
    'version': '1.1',
    'icon': '/account/static/description/l10n.png',
    'countries': ['mn'],
    'category': 'Accounting/Localizations/Account Charts',
    'author': 'NextOSP',
    'description': """
This is the module to manage the accounting chart for Mongolia.
===============================================================

    * the Mongolia Official Chart of Accounts,
    * the Tax Code Chart for Mongolia
    * the main taxes used in Mongolia

Financial requirement contributor: Baskhuu Lodoikhuu. BumanIT LLC
""",
    'depends': [
        'account',
    ],
    'auto_install': ['account'],
    'data': [
        'data/account.account.tag.csv',
        'data/vat_report.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'license': 'LGPL-3',
}

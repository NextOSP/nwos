# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Portugal - Accounting',
    'website': 'https://github.com/NextOSP',
    'icon': '/account/static/description/l10n.png',
    'countries': ['pt'],
    'version': '1.0',
    'author': 'NextOSP',
    'category': 'Accounting/Localizations/Account Charts',
    'description': 'Portugal - Accounting',
    'depends': [
        'base',
        'account',
        'base_vat',
        'account_edi_ubl_cii',
    ],
    'auto_install': ['account'],
    'data': [
        'data/account_tax_report.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_pt/static/src/helpers/*.js',
        ],
        'web.assets_frontend': [
            'l10n_pt/static/src/helpers/*.js',
        ],
    },
    'license': 'LGPL-3',
}

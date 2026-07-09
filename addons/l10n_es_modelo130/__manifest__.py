{
    'name': 'Spain - Modelo 130 Tax report',
    'website': 'https://github.com/NextOSP',
    'version': '1.0',
    'icon': '/account/static/description/l10n.png',
    'countries': ['es'],
    'category': 'Accounting/Localizations/Account Charts',
    'depends': [
        'l10n_es',
    ],
    'data': [
        'data/mod130.xml',
    ],
    'post_init_hook': '_add_mod130_tax_tags',
    'license': 'LGPL-3',
}

{
    'name': 'Italy - Sale E-invoicing',
    'version': '1.0',
    'depends': [
        'l10n_it_edi',
        'sale',
    ],
    'description': 'Sale modifications for Italy E-invoicing',
    'category': 'Accounting/Localizations/EDI',
    'website': 'https://github.com/NextOSP',
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

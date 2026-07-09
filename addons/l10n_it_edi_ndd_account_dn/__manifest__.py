{
    'name': 'Italy - E-invoicing - Bridge module between Italy NDD and Account Debit Note',
    'countries': ['it'],
    'version': '1.0',
    'depends': [
        'l10n_it_edi_ndd',
        'account_debit_note',
    ],
    'auto_install': ['l10n_it_edi_ndd'],
    'description': """
Bridge module to support the debit notes (nota di debito - NDD) by adding debit note fields.
    """,
    'category': 'Accounting/Localizations/EDI',
    'website': 'https://github.com/NextOSP',
    'data': [
        'data/invoice_it_template.xml',
    ],
    # NWOS19: bridge for l10n_it_edi_ndd, which is disabled as obsolete (its
    # functionality was absorbed into l10n_it_edi). Disabled to match.
    'installable': False,
    'license': 'LGPL-3',
}

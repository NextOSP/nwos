# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'author': 'NextOSP',
    'name': 'Romania - Send E-Factura',
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': "Bridge module for sending Romanian E-Factura to the SPV",
    'countries': ['ro'],
    'depends': ['l10n_ro_edi'],
    'data': [
        'data/ir_cron.xml',
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/account_move_send_views.xml',
    ],
    # NWOS19: obsolete - base l10n_ro_edi now natively implements the E-Factura/SPV
    # flow (l10n_ro_edi.document model, l10n_ro_edi_state/document_ids fields,
    # _l10n_ro_edi_send_invoice and the send wizard). This module fully duplicates
    # and conflicts with it.
    'installable': False,
    'auto_install': True,
    'license': 'LGPL-3',
}

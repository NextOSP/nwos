# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Vietnam - Accounting',
    'icon': '/account/static/description/l10n.png',
    'countries': ['vn'],
    'version': '2.0.5',
    'author': 'General Solutions',
    'website': 'https://github.com/NextOSP',
    'category': 'Accounting/Localizations/Account Charts',
    'description': """
This is the module to manage the accounting chart, bank information for Vietnam in NWOS.
========================================================================================

- This module applies to companies based in Vietnamese Accounting Standard (VAS)
  with Chart of account under Circular No. 200/2014/TT-BTC
- Add Vietnamese bank information (like name, bic ..) as announced and yearly updated by State Bank
  of Viet Nam (https://sbv.gov.vn/webcenter/portal/en/home/sbv/paytreasury/bankidno).
- Add VietQR feature for invoice

**Credits:**
    - General Solutions.
    - Trobz
    - Jean Nguyen - The Bean Family (https://github.com/anhjean/vietqr) for VietQR.

""",
    'depends': [
        'account_qr_code_emv',
        'base_iban',
        'base_address_extended',
        'account',
    ],
    'auto_install': ['account'],
    'post_init_hook': '_l10n_vn_set_price_precision',
    'data': [
        'data/res_country_data.xml',
        'data/res.city.csv',
        'data/account_tax_report_data.xml',
        'views/account_move_views.xml',
        'views/res_bank_views.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'license': 'LGPL-3',
}

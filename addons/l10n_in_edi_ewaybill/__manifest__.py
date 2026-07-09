# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    "name": """Indian - E-waybill""",
    "countries": ["in"],
    "version": "1.03.00",
    "category": "Accounting/Localizations/EDI",
    "depends": [
        "l10n_in_edi",
    ],
    "description": """
Indian - E-waybill
====================================
To submit E-waybill through API to the government.
We use "Tera Software Limited" as GSP

Step 1: First you need to create an API username and password in the E-waybill portal.
Step 2: Switch to company related to that GST number
Step 3: Set that username and password in NWOS (Goto: Invoicing/Accounting -> Configration -> Settings -> Indian Electronic WayBill or find "E-waybill" in search bar)
Step 4: Repeat steps 1,2,3 for all GSTIN you have in nwos. If you have a multi-company with the same GST number then perform step 1 for the first company only.
    """,
    "data": [
        "security/ir.model.access.csv",
        "data/account_edi_data.xml",
        "data/ewaybill_type_data.xml",
        "views/account_move_views.xml",
        "views/edi_pdf_report.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [
        "demo/demo_company.xml",
    ],
    # NWOS19: inherits removed account.edi.format and imports from l10n_in_edi's
    # deleted account_edi_format module; base l10n_in_edi migrated to the new EDI API.
    "installable": False,
    # not auto_install because the company can be related to the service industry
    "license": "LGPL-3",
}

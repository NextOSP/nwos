{
    "name": "Clean Documents (Quotation, PO, Delivery, Invoice)",
    "summary": "Self-contained IBM-Carbon report templates for sale quotations, "
               "purchase orders/RFQ, delivery slips and invoices, plus product "
               "images and honoring the language chosen in Review and Export",
    "category": "Sales/Sales",
    "version": "1.1",
    "author": "NextOSP",
    "depends": ["sale", "account"],
    "data": [
        "report/nwos_report_common.xml",
        "report/sale_report_image_actions.xml",
        "report/sale_report_image_templates.xml",
        "report/sale_report_clean_templates.xml",
        "report/purchase_report_clean_templates.xml",
        "report/stock_report_clean_templates.xml",
        "report/account_report_clean_templates.xml",
    ],
    "installable": True,
    # Auto-install on every database that has Sales (+ Accounting) so the clean
    # quotation template becomes the standard Print everywhere, not per-DB.
    "auto_install": True,
    "license": "LGPL-3",
}

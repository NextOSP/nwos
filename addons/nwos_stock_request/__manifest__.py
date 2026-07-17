# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Stock Request',
    'version': '1.0',
    'category': 'Inventory/Purchase',
    'summary': 'Internal stock requests with approval, feeding Replenishment and Purchase',
    'description': """
Stock Request
=============
Let internal users request items (for stock, office, project or manufacturing).
Requests go through an approval flow. Once approved, a buyer generates the
purchase / replenishment: each line is routed through the product's own routes
(Buy / Manufacture / Transfer). Lines without a vendor open a pre-filled draft
RFQ for the buyer to complete.

Features
--------
* Request header + lines with free-form specification (create the product inline).
* Draft -> To Approve -> Approved -> Done flow with refuse / cancel.
* Configurable approval amount threshold (self-approval below it).
* "Generate Purchase" runs procurement and links results back to the request.
* Dedicated security groups and record rules.
""",
    'depends': [
        'stock',
        'purchase_stock',
        'product',
        'mail',
        'analytic',
        'hr',
    ],
    'data': [
        'security/stock_request_groups.xml',
        'security/ir.model.access.csv',
        'security/stock_request_security.xml',
        'data/ir_sequence.xml',
        'data/mail_template_data.xml',
        'views/stock_request_approval_views.xml',
        'views/stock_request_views.xml',
        'views/res_config_settings_views.xml',
        'views/stock_request_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nwos_stock_request/static/src/views/stock_request_dashboard.js',
            'nwos_stock_request/static/src/views/stock_request_dashboard.xml',
            'nwos_stock_request/static/src/views/stock_request_dashboard.scss',
            'nwos_stock_request/static/src/views/stock_request_listview.js',
            'nwos_stock_request/static/src/views/stock_request_listview.xml',
        ],
    },
    'application': True,
    'installable': True,
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

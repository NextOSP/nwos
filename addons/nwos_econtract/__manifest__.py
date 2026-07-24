# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'eContract',
    'version': '1.0',
    'category': 'Sales/eContract',
    'summary': 'Contract & document templates with {{smart fields}}, generated from '
               'Sales Orders, Purchase Orders or Contacts, with PDF and e-signature',
    'description': """
eContract
=========
Design reusable contract / document **templates** in a rich-text editor using
``{{placeholder}}`` smart fields. Fields are auto-detected and typed:

* ``{{Customer Name}}``            -> text
* ``{{Sign Date:date}}``           -> date
* ``{{Total Amount:monetary}}``    -> monetary
* ``{{Agreed:boolean}}``           -> yes/no
* ``{{Signature:signature}}``      -> e-signature block

Each detected field can be **mapped** to a path on a source record
(e.g. ``partner_id.name``, ``amount_total``) so contracts pre-fill themselves.

Generate a contract from a **Sales Order**, **Purchase Order**, **Contact**, or
from scratch. Output a **PDF**, send a **portal signing link** (draw-to-sign),
and **attach** the signed PDF back onto the source document.
""",
    'depends': [
        'mail',
        'portal',
        'sale',
        'purchase',
    ],
    'data': [
        'security/econtract_groups.xml',
        'security/ir.model.access.csv',
        'security/econtract_security.xml',
        'data/ir_sequence.xml',
        'data/econtract_demo_template.xml',
        'report/econtract_report.xml',
        'wizard/econtract_generate_wizard_views.xml',
        'views/econtract_template_views.xml',
        'views/econtract_contract_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/econtract_portal_templates.xml',
        'views/econtract_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'web/static/lib/signature_pad/signature_pad.umd.js',
            'nwos_econtract/static/src/js/portal_sign.js',
            'nwos_econtract/static/src/scss/portal.scss',
        ],
        'web.assets_backend': [
            'nwos_econtract/static/src/scss/econtract.scss',
            'nwos_econtract/static/src/js/econtract_value_field.js',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
    'author': 'NextOSP',
}

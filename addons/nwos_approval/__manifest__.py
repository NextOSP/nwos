# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'Approvals',
    'version': '1.0',
    'category': 'Productivity/Approvals',
    'summary': 'Model-agnostic, configurable approval flows for any document',
    'description': """
Approvals
=========
Add an approval flow to *any* model without writing code.

An administrator picks a model (Sale Order, Purchase Order, Contract, Stock
Request, ...), the button that should require approval, the conditions under
which approval applies, and the ordered list of approval steps. The chosen
button is then blocked until the approvals complete, and re-runs automatically
once the last approver signs off.

Features
--------
* Rules per model + gated method, matched by domain and amount window.
* Ordered approval steps; approvers resolved from a group, specific users,
  the requester's manager (org chart), the department manager, or a field on
  the document itself.
* "Any one approves" / "everyone must approve" per step.
* Auto-approval below a threshold, for the first step or the whole flow.
* Approval banner injected into every form view - no per-app XML.
* Cross-application "My Approvals" inbox.
""",
    'depends': [
        'base',
        'web',
        'mail',
        'hr',
    ],
    'data': [
        'security/approval_groups.xml',
        'security/ir.model.access.csv',
        'security/approval_security.xml',
        'data/ir_sequence.xml',
        'wizard/approval_reject_wizard_views.xml',
        'views/approval_rule_views.xml',
        'views/approval_request_views.xml',
        'views/approval_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nwos_approval/static/src/components/approval_banner/approval_banner.js',
            'nwos_approval/static/src/components/approval_banner/approval_banner.xml',
            'nwos_approval/static/src/components/approval_banner/approval_banner.scss',
            'nwos_approval/static/src/views/form/approval_form_compiler.js',
            'nwos_approval/static/src/views/form/approval_form_renderer.js',
        ],
    },
    'application': True,
    'installable': True,
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

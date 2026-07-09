# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Online Members Directory',
    'category': 'Website/Website',
    'summary': 'Publish your members directory',
    'version': '1.0',
    'description': """
Publish your members/association directory publicly.
    """,
    'depends': ['website_partner', 'website_google_map', 'membership', 'website_sale'],
    'data': [
        'views/product_template_views.xml',
        'views/website_membership_templates.xml',
        'security/ir.model.access.csv',
        'security/website_membership.xml',
        # NWOS19: views/snippets.xml removed - legacy `website.snippet_options`
        # builder (data-js/we-checkbox) no longer exists in the new website builder.
    ],
    'demo': ['data/membership_demo.xml'],
    'installable': True,
    'license': 'LGPL-3',
}

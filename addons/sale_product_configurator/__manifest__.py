# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': "Sale Product Configurator",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "Configure your products",

    'description': """
Technical module:
The main purpose is to override the sale_order view to allow configuring products in the SO form.

It also enables the "optional products" feature.
    """,

    'depends': ['sale'],
    'data': [
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
    ],
    'demo': [
        'data/sale_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_product_configurator/static/src/**/*',
            # The configurator is implemented directly by `sale` now.  Loading
            # this legacy patch runs the product-template handler twice and its
            # old tuple-style many2one access sends an empty template id.
            ('remove', 'sale_product_configurator/static/src/js/sale_product_field.js'),
        ],
        'web.assets_unit_tests': [
            'sale_product_configurator/static/tests/**/*.test.js',
        ],
    },
    'auto_install': True,
    'license': 'LGPL-3',
}

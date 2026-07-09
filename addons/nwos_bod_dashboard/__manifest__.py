# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
{
    'name': 'BOD Executive Dashboard',
    'version': '1.0',
    'category': 'Productivity/Dashboard',
    'author': 'NextOSP',
    'summary': 'Board-of-Directors executive overview with a live AI assistant',
    'description': """
Executive (Board of Directors) dashboard
=========================================
A concise, sales-first overview built for decision makers:

* Only shows the sections whose app is actually installed
  (Sales, Invoicing, CRM pipeline, Purchase, Inventory, Point of Sale).
* Meaningful KPIs with period-over-period trends instead of empty noise.
* An "Ask AI" panel that answers questions over live business data,
  reusing the existing NWOS AI integration (Settings > Integrations > AI).
""",
    'depends': ['base_setup', 'mail_bot', 'web'],
    'data': [
        'views/bod_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nwos_bod_dashboard/static/src/**/*.js',
            'nwos_bod_dashboard/static/src/**/*.xml',
            'nwos_bod_dashboard/static/src/**/*.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

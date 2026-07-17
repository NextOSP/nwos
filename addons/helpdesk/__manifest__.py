# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk',
    'version': '1.0',
    'category': 'Services/Helpdesk',
    'sequence': 50,
    'summary': 'Track customer support tickets and team performance',
    'website': 'https://github.com/NextOSP',
    'depends': [
        'base_setup',
        'mail',
        'portal',
        'rating',
        'resource',
        'web',
        'digest',
    ],
    'data': [
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',

        'data/ir_sequence_data.xml',
        'data/helpdesk_stage_data.xml',
        'data/helpdesk_team_data.xml',
        'data/helpdesk_sla_data.xml',
        'data/ir_cron_data.xml',
        'data/digest_data.xml',

        'views/helpdesk_stage_views.xml',
        'views/helpdesk_tag_views.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_sla_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_dashboard_views.xml',
        'views/helpdesk_templates.xml',
        'views/helpdesk_menus.xml',
    ],
    'demo': [
        'data/helpdesk_demo.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'helpdesk/static/src/scss/helpdesk.scss',
            'helpdesk/static/src/views/helpdesk_dashboard.scss',
            'helpdesk/static/src/views/helpdesk_dashboard.js',
            'helpdesk/static/src/views/helpdesk_dashboard.xml',
            'helpdesk/static/src/views/helpdesk_dashboard_kanban.js',
        ],
    },
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

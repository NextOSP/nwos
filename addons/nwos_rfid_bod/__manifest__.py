# -*- coding: utf-8 -*-
{
    'name': 'Nextwaves Kit BOD Dashboard',
    'version': '1.4',
    'category': 'Productivity/Dashboard',
    'summary': 'Executive Nextwaves Kit KPIs and scheduled monthly PDF report',
    'depends': ['nwos_rfid_service', 'nwos_bod_dashboard'],
    'data': [
        'data/ir_cron_data.xml',
        'report/rfid_bod_report.xml',
        'views/res_config_settings_views.xml',
        'views/bod_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nwos_rfid_bod/static/src/**/*.js',
            'nwos_rfid_bod/static/src/**/*.xml',
            'nwos_rfid_bod/static/src/**/*.scss',
        ],
    },
    'installable': True,
    'license': 'LGPL-3',
    'author': 'NextOSP',
}

# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'NextBot',
    'version': '1.2',
    'category': 'Productivity/Discuss',
    'summary': 'Add NextBot in discussions',
    'website': 'https://github.com/NextOSP',
    'depends': ['mail'],
    'auto_install': True,
    'installable': True,
    'data': [
        'views/res_users_views.xml',
        'data/mailbot_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mail_bot/static/src/core/nextbot_channel_commands.js',
            'mail_bot/static/src/core/nextbot_action_links.js',
            'mail_bot/static/src/scss/nwosbot_style.scss',
        ],
    },
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

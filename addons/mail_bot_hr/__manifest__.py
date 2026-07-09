# -*- coding: utf-8 -*-
{
    'name': "NextBot - HR",
    'summary': """Bridge module between hr and mailbot.""",
    'description': """This module adds the NextBot state and notifications in the user form modified by hr.""",
    'website': "https://github.com/NextOSP",
    'category': 'Productivity/Discuss',
    'version': '1.0',
    'depends': ['mail_bot', 'hr'],
    'installable': True,
    'auto_install': True,
    'data': [
        'views/res_users_views.xml',
    ],
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

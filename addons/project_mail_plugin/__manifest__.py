# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

{
    'name': 'Project Mail Plugin',
    'version': '1.0',
    'category': 'Services/Project',
    'sequence': 5,
    'summary': 'Integrate your inbox with projects',
    'description': "Turn emails received in your mailbox into tasks and log their content as internal notes.",
    'data': [
        'views/project_task_views.xml'
    ],
    'website': 'https://github.com/NextOSP',
    'depends': [
        'project',
        'mail_plugin',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'NextOSP',
    'license': 'LGPL-3',
}

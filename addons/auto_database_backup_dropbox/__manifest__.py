# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': "Automatic Database Backup To Dropbox",
    'summary': """This module allows will generate automatic backup of databases and store to dropbox""",
    'version': '4.0.1.0',
    'author': "NextOSP",
    'website': "https://github.com/NextOSP",
    'category': 'Tools',
    'depends': ['auto_database_backup'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/authentication_wizard_views.xml',
        'views/db_backup_configure_views.xml',
    ],
    'license': 'LGPL-3',
    'external_dependencies': {'python': ['dropbox']},
    'installable': True,
    'auto_install': False,
    'application': False,
}

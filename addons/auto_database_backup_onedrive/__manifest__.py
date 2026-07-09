# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': "Automatic Database Backup To Onedrive",
    'summary': """This module allows will generate automatic backup of databases and store to onedrive""",
    'version': '4.0.1.0',
    'author': "NextOSP",
    'website': "https://github.com/NextOSP",
    'category': 'Tools',
    'depends': ['auto_database_backup'],
    'data': [
        'views/db_backup_configure_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

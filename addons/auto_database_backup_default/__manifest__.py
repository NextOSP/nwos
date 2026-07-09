# Part of NextOSP. See LICENSE file for full copyright & licensing details.
{
    'name': "Daily Backup & Easy Restore (Standard)",
    'summary': """Turnkey daily backup of the whole database and filestore"""
               """ to Local + Amazon S3, with an in-app restore wizard""",
    'description': """
Standard, turnkey backup feature for Flectra.

On install this module:
  * auto-creates a **daily** backup configuration for the current database that
    dumps *everything* (SQL database + the whole filestore / attachments) as a
    single ``zip`` archive,
  * seeds both a **Local** and an **Amazon S3** destination (fill the S3
    credentials once to activate off-site backups),
  * enables the daily backup scheduled action.

It also adds an in-app **Restore Backup** wizard: pick a backup from the Local
or S3 destination, give it a new database name, and it restores the database and
filestore in one click (safely, into a new database - it never overwrites the
running one).
    """,
    'version': '4.0.1.0',
    'author': "NextOSP",
    'website': "https://github.com/NextOSP",
    'category': 'Tools',
    'depends': [
        'auto_database_backup',
        'auto_database_backup_s3',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/db_backup_restore_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

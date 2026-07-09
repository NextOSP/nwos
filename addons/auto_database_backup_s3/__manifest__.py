# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################
{
    'name': "Automatic Database Backup to Amazon S3 (and S3-compatible storage)",
    'summary': """Generate automatic backup of databases (including the filestore)"""
               """ and store them on Amazon S3 or any S3-compatible service""",
    'description': """
This module adds an Amazon S3 destination to the Automatic Database Backup suite.

Each backup uses the standard Flectra database dump, so the generated ``zip``
archive contains the SQL dump, the manifest and the whole filestore
(all attachments and uploaded files) in a single object uploaded to S3.

It works with Amazon S3 as well as any S3-compatible storage (MinIO, Wasabi,
DigitalOcean Spaces, Backblaze B2, ...) via the optional Endpoint URL field.

Requires the ``boto3`` python library: ``pip install boto3``.
    """,
    'version': '4.0.1.0',
    'author': "NextOSP",
    'website': "https://github.com/NextOSP",
    'category': 'Tools',
    'depends': ['auto_database_backup'],
    'external_dependencies': {'python': ['boto3']},
    'data': [
        'views/db_backup_configure_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

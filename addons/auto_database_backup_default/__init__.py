# Part of NextOSP. See LICENSE file for full copyright & licensing details.

import logging
import os

from nwos.tools import config

from . import wizard

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Seed a standard daily backup for the current database and enable the cron.

    Two destinations are created so the same daily run stores the backup both
    locally (works immediately) and to Amazon S3 (once credentials are filled).
    Idempotent: existing configurations for this database are left untouched.
    """
    dbname = env.cr.dbname
    Config = env['db.backup.configure']

    if not Config.search([('db_name', '=', dbname),
                          ('backup_destination', '=', 'local')], limit=1):
        Config.create({
            'name': 'Daily Local Backup',
            'db_name': dbname,
            'backup_format': 'zip',  # zip bundles the SQL dump + the whole filestore
            'backup_destination': 'local',
            'backup_path': os.path.join(config['data_dir'], 'backups', dbname),
            'auto_remove': True,
            'days_to_remove': 30,
        })
        _logger.info('Seeded daily Local backup config for %s', dbname)

    if not Config.search([('db_name', '=', dbname),
                          ('backup_destination', '=', 'amazon_s3')], limit=1):
        Config.create({
            'name': 'Daily S3 Backup (enter credentials to activate)',
            'db_name': dbname,
            'backup_format': 'zip',
            'backup_destination': 'amazon_s3',
            's3_region': 'us-east-1',
            'auto_remove': True,
            'days_to_remove': 30,
        })
        _logger.info('Seeded daily S3 backup config for %s', dbname)

    cron = env.ref('auto_database_backup.ir_cron_auto_db_backup',
                   raise_if_not_found=False)
    if cron:
        cron.write({
            'active': True,
            'interval_number': 1,
            'interval_type': 'days',
        })
        _logger.info('Enabled daily automatic backup cron')

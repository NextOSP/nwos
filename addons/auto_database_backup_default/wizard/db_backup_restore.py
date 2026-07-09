# Part of NextOSP. See LICENSE file for full copyright & licensing details.

import logging
import os
import shutil
import tempfile

import nwos
from nwos import _, api, fields, models
from nwos.exceptions import UserError
from nwos.service import db

_logger = logging.getLogger(__name__)


class DbBackupRestore(models.TransientModel):
    _name = 'db.backup.restore'
    _description = 'Restore Database Backup'

    config_id = fields.Many2one(
        'db.backup.configure', string='Backup Source', required=True,
        help='Backup configuration whose destination (Local or S3) holds the backups')
    backup_destination = fields.Selection(related='config_id.backup_destination')
    backup_file = fields.Char(
        string='Backup File', required=True,
        help='File name of the backup to restore (defaults to the most recent one)')
    available_backups = fields.Text(
        string='Available Backups', readonly=True,
        help='Backups found in the selected destination, newest first')
    new_dbname = fields.Char(
        string='Restore As', required=True,
        help='Name of the NEW database to create from the backup. '
             'It must not already exist - the running database is never overwritten.')
    master_pwd = fields.Char(string='Master Password', required=True)
    neutralize = fields.Boolean(
        string='Neutralize Restored Database', default=True,
        help='Disable outgoing email, scheduled actions and other external '
             'integrations in the restored copy (recommended for test restores)')

    def _list_backups(self):
        """Return backup file names in the config's destination, newest first."""
        self.ensure_one()
        cfg = self.config_id
        if cfg.backup_destination == 'local':
            path = cfg.backup_path
            if path and os.path.isdir(path):
                files = [f for f in os.listdir(path)
                         if os.path.isfile(os.path.join(path, f))]
                files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)),
                           reverse=True)
                return files
        elif cfg.backup_destination == 'amazon_s3':
            client = cfg._get_s3_client()
            prefix = (cfg.s3_folder.strip('/') + '/') if cfg.s3_folder else ''
            objs = []
            paginator = client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
                for o in page.get('Contents', []):
                    objs.append((o['Key'], o['LastModified']))
            objs.sort(key=lambda x: x[1], reverse=True)
            return [k[len(prefix):] if prefix and k.startswith(prefix) else k
                    for k, _dt in objs]
        return []

    @api.onchange('config_id')
    def _onchange_config_id(self):
        """List available backups and preselect the most recent one."""
        for wizard in self:
            wizard.backup_file = False
            wizard.available_backups = False
            if not wizard.config_id:
                continue
            if wizard.config_id.backup_destination not in ('local', 'amazon_s3'):
                wizard.available_backups = _(
                    'Restore is only supported for Local and Amazon S3 destinations.')
                continue
            try:
                backups = wizard._list_backups()
            except Exception as e:  # noqa: BLE001 - surface any destination error
                wizard.available_backups = _('Could not list backups: %s', e)
                continue
            if backups:
                wizard.backup_file = backups[0]
                wizard.available_backups = '\n'.join(backups[:50])
            else:
                wizard.available_backups = _('No backups found in this destination.')

    def _fetch_backup(self, dest_path):
        """Download/copy the selected backup into dest_path (a local file path)."""
        self.ensure_one()
        cfg = self.config_id
        if cfg.backup_destination == 'local':
            src = os.path.join(cfg.backup_path, self.backup_file)
            if not os.path.isfile(src):
                raise UserError(_("Backup file not found: %s", src))
            shutil.copyfile(src, dest_path)
        elif cfg.backup_destination == 'amazon_s3':
            client = cfg._get_s3_client()
            prefix = (cfg.s3_folder.strip('/') + '/') if cfg.s3_folder else ''
            client.download_file(cfg.s3_bucket, prefix + self.backup_file, dest_path)
        else:
            raise UserError(_(
                "Restore is only supported for Local and Amazon S3 destinations."))

    def action_restore(self):
        self.ensure_one()
        if not nwos.tools.config.verify_admin_password(self.master_pwd):
            raise UserError(_("Incorrect master password."))
        new_db = (self.new_dbname or '').strip()
        if not new_db:
            raise UserError(_("Please provide a name for the restored database."))
        if new_db in db.list_dbs():
            raise UserError(_(
                "A database named '%s' already exists. Choose a different name - "
                "the restore never overwrites an existing database.", new_db))

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.%s' % self.config_id.backup_format)
        os.close(tmp_fd)
        try:
            self._fetch_backup(tmp_path)
            # restore_db recreates the database and moves the filestore into place
            db.restore_db(new_db, tmp_path, copy=True,
                          neutralize_database=self.neutralize)
        except UserError:
            raise
        except Exception as e:  # noqa: BLE001
            _logger.exception('Restore failed for %s', new_db)
            raise UserError(_("Restore failed: %s", e))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Restore Completed"),
                'message': _(
                    "Database '%s' was restored (database + filestore). "
                    "Log in to it from the database selector.", new_db),
                'sticky': True,
                'type': 'success',
            }
        }

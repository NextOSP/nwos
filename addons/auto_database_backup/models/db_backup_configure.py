# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################

import datetime
import logging
import os

import nwos
from nwos import _, api, fields, models
from nwos.exceptions import ValidationError
from nwos.service import db

_logger = logging.getLogger(__name__)


class AutoDatabaseBackup(models.Model):
    _name = 'db.backup.configure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Automatic Database Backup'

    name = fields.Char(string='Name', required=True)
    db_name = fields.Char(string='Database Name', required=True)
    backup_format = fields.Selection([
        ('zip', 'Zip'),
        ('dump', 'Dump')
    ], string='Backup Format', default='zip', required=True)
    backup_destination = fields.Selection([
        ('local', 'Local Storage')
    ], string='Backup Destination', default='local')
    backup_path = fields.Char(string='Backup Path',
                              help='Local storage directory path')
    active = fields.Boolean(default=True)
    auto_remove = fields.Boolean(string='Remove Old Backups')
    days_to_remove =\
        fields.Integer(string='Remove After',
                       help='Automatically delete stored backups'
                            ' after this specified number of days')
    notify_user =\
        fields.Boolean(string='Notify User',
                       help='Send an email notification to user '
                            'when the backup operation is successful or failed')
    user_id = fields.Many2one('res.users', string='User')
    backup_filename = fields.Char(string='Backup Filename',
                                  help='For Storing generated backup filename')
    generated_exception =\
        fields.Char(string='Exception',
                    help='Exception Encountered while Backup generation')
    last_backup_state = fields.Selection([
        ('never', 'Never Run'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Last Backup Status', default='never', readonly=True)
    last_backup_date = fields.Datetime(string='Last Backup Date', readonly=True)
    last_backup_message = fields.Char(string='Last Backup Message', readonly=True)

    @api.constrains('db_name')
    def _check_db_credentials(self):
        """
        Validate entered database name and master password
        """
        database_list = db.list_dbs()
        if self.db_name not in database_list:
            raise ValidationError(_("Invalid Database Name!"))

    def _record_backup_file(self, filename, storage_path, file_size=0, modified_at=None):
        self.ensure_one()
        BackupFile = self.env['db.backup.file'].sudo()
        values = {
            'config_id': self.id,
            'name': filename,
            'storage_path': storage_path,
            'file_size': file_size or 0,
            'modified_at': modified_at or fields.Datetime.now(),
            'exists': True,
        }
        record = BackupFile.search([
            ('config_id', '=', self.id),
            ('name', '=', filename),
            ('storage_path', '=', storage_path),
        ], limit=1)
        if record:
            record.write(values)
        else:
            record = BackupFile.create(values)
        return record

    def _mark_backup_success(self, filename):
        self.write({
            'backup_filename': filename,
            'generated_exception': False,
            'last_backup_state': 'success',
            'last_backup_date': fields.Datetime.now(),
            'last_backup_message': _("Backup completed successfully."),
        })

    def _mark_backup_failure(self, error):
        error_message = str(error or _("Unknown error"))
        self.write({
            'generated_exception': error_message,
            'last_backup_state': 'failed',
            'last_backup_date': fields.Datetime.now(),
            'last_backup_message': error_message,
        })
        self.message_post(body=_("Database backup failed: %s", error_message))
        user = self.user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
        activity_type = self.env.ref('mail.mail_activity_data_warning', raise_if_not_found=False)
        if user and activity_type:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=user.id,
                summary=_("Database backup failed"),
                note=error_message,
            )

    def _sync_local_backup_files(self):
        self.ensure_one()
        BackupFile = self.env['db.backup.file'].sudo()
        existing = BackupFile.search([('config_id', '=', self.id)])
        seen_names = set()
        if self.backup_path and os.path.isdir(self.backup_path):
            for filename in os.listdir(self.backup_path):
                storage_path = os.path.join(self.backup_path, filename)
                if not os.path.isfile(storage_path):
                    continue
                seen_names.add(filename)
                self._record_backup_file(
                    filename,
                    storage_path,
                    file_size=os.path.getsize(storage_path),
                    modified_at=fields.Datetime.to_datetime(
                        datetime.datetime.fromtimestamp(os.path.getmtime(storage_path))
                    ),
                )
        existing.filtered(lambda backup: backup.name not in seen_names).write({'exists': False})

    def _sync_s3_backup_files(self):
        self.ensure_one()
        if not hasattr(self, '_get_s3_client'):
            return
        if not (self.s3_access_key and self.s3_secret_key and self.s3_bucket):
            raise ValidationError(_("S3 credentials are not configured yet."))
        BackupFile = self.env['db.backup.file'].sudo()
        existing = BackupFile.search([('config_id', '=', self.id)])
        seen_paths = set()
        client = self._get_s3_client()
        prefix = (self.s3_folder.strip('/') + '/') if getattr(self, 's3_folder', False) else ''
        paginator = client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
            for item in page.get('Contents', []):
                key = item['Key']
                filename = key[len(prefix):] if prefix and key.startswith(prefix) else key
                modified_at = item.get('LastModified')
                if modified_at and modified_at.tzinfo:
                    modified_at = modified_at.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                seen_paths.add(key)
                self._record_backup_file(
                    filename,
                    key,
                    file_size=item.get('Size') or 0,
                    modified_at=modified_at,
                )
        existing.filtered(lambda backup: backup.storage_path not in seen_paths).write({'exists': False})

    def action_sync_backup_files(self, raise_on_error=True):
        errors = []
        for record in self:
            try:
                if record.backup_destination == 'local':
                    record._sync_local_backup_files()
                elif record.backup_destination == 'amazon_s3':
                    record._sync_s3_backup_files()
            except Exception as error:
                record._mark_backup_failure(error)
                message = _("Could not list backups for %(name)s: %(error)s", name=record.display_name, error=error)
                errors.append(message)
                if raise_on_error:
                    raise ValidationError(message)
        return errors

    def action_view_backup_files(self):
        self.action_sync_backup_files(
            raise_on_error=not self.env.context.get('ignore_backup_listing_errors')
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Backup Files"),
            'res_model': 'db.backup.file',
            'view_mode': 'list,form',
            'domain': [('config_id', 'in', self.ids)],
            'context': {'search_default_existing': 1},
        }

    def create_database_backup(self):
        mail_template_success = self.env.ref('auto_database_backup.'
                                             'mail_template_data_db_backup_successful')
        mail_template_failed = self.env.ref('auto_database_backup.'
                                            'mail_template_data_db_backup_failed')
        backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = "%s_%s.%s" % (self.db_name, backup_time, self.backup_format)
        # Local backup
        if self.backup_destination == 'local':
            try:
                if not os.path.isdir(self.backup_path):
                    os.makedirs(self.backup_path)
                backup_file = os.path.join(self.backup_path, backup_filename)
                with open(backup_file, "wb") as f:
                    nwos.service.db.dump_db(self.db_name, f, self.backup_format)
                self._record_backup_file(
                    backup_filename,
                    backup_file,
                    file_size=os.path.getsize(backup_file),
                    modified_at=fields.Datetime.now(),
                )
                # remove older backups
                if self.auto_remove:
                    for filename in os.listdir(self.backup_path):
                        file = os.path.join(self.backup_path, filename)
                        create_time = \
                            datetime.datetime.fromtimestamp(os.path.getctime(file))
                        backup_duration = datetime.datetime.utcnow() - create_time
                        if backup_duration.days >= self.days_to_remove:
                            os.remove(file)
                self._mark_backup_success(backup_filename)
                if self.notify_user:
                    mail_template_success.send_mail(self.id, force_send=True)
            except Exception as e:
                self._mark_backup_failure(e)
                _logger.info('Backup Exception: %s', e)
                if self.notify_user:
                    mail_template_failed.send_mail(self.id, force_send=True)
        else:
            method_name = 'backup_to_' + self.backup_destination
            getattr(self, method_name)(self)

    def action_backup_now(self):
        backups = []
        for record in self:
            record.generated_exception = False
            record.create_database_backup()
            if record.generated_exception:
                raise ValidationError(_(
                    "Backup failed for %(name)s: %(error)s",
                    name=record.display_name,
                    error=record.generated_exception,
                ))
            backups.append(record.backup_filename or record.display_name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Backup Started"),
                'message': _("Backup created: %s", ", ".join(backups)),
                'sticky': False,
                'type': 'success',
            },
        }

    def _schedule_auto_backup(self):
        """
        Function for generating and storing backup
        Database backup for all the active records in
         backup configuration model will be created
        """
        records = self.search([])
        for rec in records:
            rec.create_database_backup()


class Module(models.Model):
    _inherit = "ir.module.module"

    def button_immediate_upgrade(self):
        """
        Upgrade the selected module(s) immediately and fully,
        return the next res.config action to execute
        """
        auto_backup = self.env['ir.config_parameter'].sudo().get_param('auto_backup')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Upgrade Confirmation',
            'res_model': 'module.upgrade.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'auto_backup': auto_backup}
        }

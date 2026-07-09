# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################

import datetime
import logging
import tempfile

import nwos
from nwos import _, fields, models
from nwos.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception
    _logger.debug("Cannot import 'boto3'. Please install it to use the S3 backup destination.")


class AutoDatabaseBackup(models.Model):
    _inherit = 'db.backup.configure'
    _description = 'Automatic Database Backup'

    backup_destination = fields.Selection(selection_add=[('amazon_s3', 'Amazon S3')],
                                          ondelete={'amazon_s3': 'set default'})

    s3_access_key = fields.Char(string='S3 Access Key', copy=False)
    s3_secret_key = fields.Char(string='S3 Secret Key', copy=False)
    s3_bucket = fields.Char(string='S3 Bucket')
    s3_region = fields.Char(string='S3 Region', default='us-east-1',
                            help='AWS region of the bucket, e.g. us-east-1')
    s3_folder = fields.Char(string='S3 Folder',
                            help='Optional key prefix (folder) inside the bucket')
    s3_endpoint_url = fields.Char(
        string='S3 Endpoint URL',
        help='Leave empty for Amazon S3. Set the endpoint URL to use an '
             'S3-compatible service such as MinIO, Wasabi, DigitalOcean Spaces '
             'or Backblaze B2, e.g. https://s3.wasabisys.com')

    def _get_s3_client(self):
        """
        Build a boto3 S3 client from the configured credentials.
        Works with Amazon S3 and any S3-compatible endpoint.
        """
        self.ensure_one()
        if boto3 is None:
            raise UserError(_("The 'boto3' python library is required for S3 backups. "
                              "Please install it with: pip install boto3"))
        return boto3.client(
            's3',
            aws_access_key_id=self.s3_access_key,
            aws_secret_access_key=self.s3_secret_key,
            region_name=self.s3_region or None,
            endpoint_url=self.s3_endpoint_url or None,
        )

    def test_s3_connection(self):
        """
        Test the S3 connection and bucket access using the entered credentials.
        """
        try:
            client = self._get_s3_client()
            client.head_bucket(Bucket=self.s3_bucket)
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("S3 Exception: %s", e))
        title = _("Connection Test Succeeded!")
        message = _("Everything seems properly set up!")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'sticky': False,
            }
        }

    def backup_to_amazon_s3(self, rec):
        mail_template_success = self.env.ref('auto_database_backup.'
                                             'mail_template_data_db_backup_successful')
        mail_template_failed = self.env.ref('auto_database_backup.'
                                            'mail_template_data_db_backup_failed')
        # Mark missing S3 credentials as a visible backup failure so admins see it.
        if not (rec.s3_access_key and rec.s3_secret_key and rec.s3_bucket):
            _logger.info('S3 backup skipped for %s: credentials not configured yet', rec.db_name)
            rec._mark_backup_failure(_('S3 credentials are not configured yet.'))
            return
        backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = "%s_%s.%s" % (rec.db_name, backup_time, rec.backup_format)
        prefix = (rec.s3_folder.strip('/') + '/') if rec.s3_folder else ''
        key = prefix + backup_filename
        try:
            client = rec._get_s3_client()
            # The zip dump bundles dump.sql, manifest.json and the whole filestore.
            with tempfile.NamedTemporaryFile(suffix='.%s' % rec.backup_format) as tmp:
                nwos.service.db.dump_db(rec.db_name, tmp, rec.backup_format)
                tmp.seek(0)
                file_size = tmp.tell()
                tmp.seek(0, 2)
                file_size = tmp.tell() or file_size
                tmp.seek(0)
                client.upload_fileobj(tmp, rec.s3_bucket, key)
            rec._record_backup_file(backup_filename, key, file_size=file_size,
                                    modified_at=fields.Datetime.now())
            if rec.auto_remove:
                now = datetime.datetime.now(datetime.timezone.utc)
                paginator = client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=rec.s3_bucket, Prefix=prefix):
                    for obj in page.get('Contents', []):
                        diff_days = (now - obj['LastModified']).days
                        if diff_days >= rec.days_to_remove:
                            client.delete_object(Bucket=rec.s3_bucket, Key=obj['Key'])
            rec._mark_backup_success(backup_filename)
            if rec.notify_user:
                mail_template_success.send_mail(rec.id, force_send=True)
        except Exception as e:
            rec._mark_backup_failure(e)
            _logger.info('S3 Exception: %s', e)
            if rec.notify_user:
                mail_template_failed.send_mail(rec.id, force_send=True)

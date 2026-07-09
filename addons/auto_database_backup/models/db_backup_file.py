# Part of NextOSP. See LICENSE file for full copyright & licensing details.

from nwos import api, fields, models


class DatabaseBackupFile(models.Model):
    _name = 'db.backup.file'
    _description = 'Database Backup File'
    _order = 'modified_at desc, id desc'

    name = fields.Char(required=True)
    config_id = fields.Many2one(
        'db.backup.configure',
        string='Backup Configuration',
        required=True,
        ondelete='cascade',
        index=True,
    )
    db_name = fields.Char(related='config_id.db_name', store=True, readonly=True)
    backup_destination = fields.Selection(
        related='config_id.backup_destination',
        store=True,
        readonly=True,
    )
    storage_path = fields.Char(string='Storage Path / Key', readonly=True)
    file_size = fields.Integer(string='Size (bytes)', readonly=True)
    file_size_human = fields.Char(string='Size', compute='_compute_file_size_human')
    modified_at = fields.Datetime(string='Modified At', readonly=True)
    exists = fields.Boolean(default=True, readonly=True)

    _config_file_uniq = models.Constraint(
        'unique(config_id, name, storage_path)',
        'A backup file is already registered for this configuration.',
    )

    @api.depends('file_size')
    def _compute_file_size_human(self):
        for record in self:
            size = float(record.file_size or 0)
            unit = 'B'
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024 or unit == 'TB':
                    break
                size /= 1024
            record.file_size_human = f"{size:.1f} {unit}" if unit != 'B' else f"{int(size)} B"

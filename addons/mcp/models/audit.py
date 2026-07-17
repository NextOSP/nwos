# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import datetime

from nwos import api, fields, models


class McpAuditLog(models.Model):
    _name = 'mcp.audit.log'
    _description = 'MCP Audit Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'operation'

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='restrict')
    request_id = fields.Char(index=True)
    client_name = fields.Char()
    session_id = fields.Char(index=True)
    ip_address = fields.Char()
    model_name = fields.Char(index=True)
    operation = fields.Char(required=True, index=True)
    record_ids = fields.Text()
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
    ], required=True, default='success', index=True)
    duration_ms = fields.Float()
    error_category = fields.Char()
    error_message = fields.Char()

    @api.model
    @api.private
    def log_event(self, **values):
        """Write a redacted metadata-only event without requiring user ACLs."""
        allowed = {
            'user_id', 'request_id', 'client_name', 'session_id', 'ip_address',
            'model_name', 'operation', 'record_ids', 'status', 'duration_ms',
            'error_category', 'error_message',
        }
        vals = {key: value for key, value in values.items() if key in allowed}
        vals.setdefault('user_id', self.env.uid)
        vals.setdefault('status', 'success')
        if vals.get('error_message'):
            # Exception messages can contain record names, values, or connector
            # payload fragments. Keep the audit trail metadata-only.
            vals['error_message'] = 'Operation failed; see the server log for details.'
        if 'record_ids' in vals and not isinstance(vals['record_ids'], str):
            vals['record_ids'] = ','.join(
                str(record_id) for record_id in (vals['record_ids'] or [])
            )[:2000] or False
        return self.sudo().create(vals)

    @api.model
    def _cron_purge_old_logs(self):
        params = self.env['ir.config_parameter'].sudo()
        try:
            retention_days = max(1, int(params.get_param('mcp.audit_retention_days', 90)))
        except (TypeError, ValueError):
            retention_days = 90
        cutoff = fields.Datetime.now() - datetime.timedelta(days=retention_days)
        # This is an append-only technical log with no unlink hooks. A direct
        # bounded-condition delete avoids materializing months of audit rows.
        self.env.cr.execute(
            'DELETE FROM mcp_audit_log WHERE create_date < %s',
            [cutoff],
        )
        self.invalidate_model()
        return True

    @api.autovacuum
    def _gc_mcp_audit_logs(self):
        self._cron_purge_old_logs()

# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import datetime
import hashlib
import json
import secrets

from nwos import api, fields, models, _
from nwos.exceptions import AccessError, ValidationError


def _canonical_digest(value):
    serialized = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class McpConfirmationToken(models.Model):
    _name = 'mcp.confirmation.token'
    _description = 'MCP Confirmation Token'
    _order = 'expires_at desc'
    _rec_name = 'model_name'

    token_hash = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade', readonly=True)
    operation = fields.Selection([
        ('delete', 'Delete'),
        ('action', 'Workflow Action'),
    ], required=True, index=True, readonly=True)
    model_name = fields.Char(required=True, index=True, readonly=True)
    record_ids = fields.Text(required=True, readonly=True)
    method_name = fields.Char(readonly=True)
    arguments_digest = fields.Char(required=True, readonly=True)
    version_digest = fields.Char(required=True, readonly=True)
    expires_at = fields.Datetime(required=True, index=True, readonly=True)
    consumed_at = fields.Datetime(index=True, readonly=True)
    preview = fields.Text(readonly=True)

    _token_hash_unique = models.Constraint(
        'UNIQUE (token_hash)', 'MCP confirmation tokens must be unique.'
    )

    @api.model
    def _record_version_digest(self, model_name, record_ids):
        if model_name not in self.env:
            raise ValidationError(_('Unknown model: %s', model_name))
        records = self.env[model_name].browse(record_ids).exists()
        if set(records.ids) != set(record_ids):
            raise ValidationError(_('One or more records no longer exist.'))
        records.check_access('read')
        if 'write_date' in records._fields:
            versions = records.read(['write_date'])
        else:
            field_info = records.fields_get(attributes=['type', 'store'])
            version_fields = sorted(
                field_name
                for field_name, description in field_info.items()
                if description.get('store')
                and description.get('type') not in ('binary', 'one2many', 'many2many')
                and field_name != 'id'
            )
            versions = records.read(version_fields)
        return _canonical_digest(sorted(versions, key=lambda item: item['id']))

    @api.model
    @api.private
    def issue(self, operation, model_name, record_ids, method_name=None,
              arguments=None, preview=None, ttl=None):
        record_ids = sorted({int(record_id) for record_id in record_ids})
        if not record_ids:
            raise ValidationError(_('At least one record is required.'))
        if operation not in ('delete', 'action'):
            raise ValidationError(_('Unsupported confirmation operation.'))
        if ttl is None:
            try:
                ttl = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mcp.confirmation_ttl', 300
                ))
            except (TypeError, ValueError):
                ttl = 300
        ttl = min(max(ttl, 30), 3600)
        raw_token = secrets.token_urlsafe(32)
        expires_at = fields.Datetime.now() + datetime.timedelta(seconds=ttl)
        arguments = arguments or {}
        self.sudo().create({
            'token_hash': _token_hash(raw_token),
            'user_id': self.env.uid,
            'company_id': self.env.company.id,
            'operation': operation,
            'model_name': model_name,
            'record_ids': json.dumps(record_ids),
            'method_name': method_name,
            'arguments_digest': _canonical_digest(arguments),
            'version_digest': self._record_version_digest(model_name, record_ids),
            'expires_at': expires_at,
            # Never persist business values from the immediate preview response.
            'preview': json.dumps({'count': len(record_ids)}),
        })
        return {
            'confirmation_token': raw_token,
            'expires_at': fields.Datetime.to_string(expires_at),
        }

    @api.model
    @api.private
    def consume(self, token, operation, model_name, record_ids,
                method_name=None, arguments=None):
        if not token:
            raise ValidationError(_('A confirmation token is required.'))
        token_record = self.sudo().search([('token_hash', '=', _token_hash(token))], limit=1)
        if not token_record:
            raise ValidationError(_('The confirmation token is invalid.'))
        self.env.cr.execute(
            'SELECT id FROM mcp_confirmation_token WHERE id = %s FOR UPDATE',
            [token_record.id],
        )
        token_record.invalidate_recordset()
        now = fields.Datetime.now()
        expected_ids = sorted({int(record_id) for record_id in record_ids})
        actual_ids = json.loads(token_record.record_ids)
        if token_record.user_id.id != self.env.uid or token_record.company_id != self.env.company:
            raise AccessError(_('The confirmation token belongs to a different user or company.'))
        if token_record.consumed_at:
            raise ValidationError(_('The confirmation token has already been used.'))
        if token_record.expires_at <= now:
            raise ValidationError(_('The confirmation token has expired.'))
        if (
            token_record.operation != operation
            or token_record.model_name != model_name
            or actual_ids != expected_ids
            or (token_record.method_name or None) != (method_name or None)
            or token_record.arguments_digest != _canonical_digest(arguments or {})
        ):
            raise ValidationError(_('The confirmation token does not match this operation.'))
        if token_record.version_digest != self._record_version_digest(model_name, expected_ids):
            raise ValidationError(_('The records changed after the operation was previewed.'))
        token_record.write({'consumed_at': now})
        return True

    @api.autovacuum
    def _gc_mcp_confirmation_tokens(self):
        cutoff = fields.Datetime.now() - datetime.timedelta(days=1)
        self.sudo().search([
            '|', ('expires_at', '<', cutoff), ('consumed_at', '<', cutoff),
        ]).unlink()


class McpDownloadToken(models.Model):
    _name = 'mcp.download.token'
    _description = 'MCP Download Token'
    _order = 'expires_at desc'
    _rec_name = 'name'

    token_hash = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade', readonly=True)
    company_ids_json = fields.Text(readonly=True)
    model_name = fields.Char(index=True, readonly=True)
    res_id = fields.Integer(index=True, readonly=True)
    record_ids = fields.Text(readonly=True)
    field_name = fields.Char(readonly=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='cascade', readonly=True)
    report_id = fields.Many2one('ir.actions.report', ondelete='cascade', readonly=True)
    name = fields.Char(required=True, readonly=True)
    mimetype = fields.Char(default='application/octet-stream', readonly=True)
    payload = fields.Binary(attachment=True, readonly=True)
    expires_at = fields.Datetime(required=True, index=True, readonly=True)
    consumed_at = fields.Datetime(index=True, readonly=True)

    _download_token_hash_unique = models.Constraint(
        'UNIQUE (token_hash)', 'MCP download tokens must be unique.'
    )

    @api.model
    @api.private
    def issue(self, name, mimetype=None, payload=None, attachment=None,
              report=None, model_name=None, res_id=None, record_ids=None,
              field_name=None, ttl=None):
        if ttl is None:
            try:
                ttl = int(self.env['ir.config_parameter'].sudo().get_param('mcp.download_ttl', 300))
            except (TypeError, ValueError):
                ttl = 300
        ttl = min(max(ttl, 30), 3600)
        raw_token = secrets.token_urlsafe(32)
        expires_at = fields.Datetime.now() + datetime.timedelta(seconds=ttl)
        company_ids = sorted(self.env.companies.ids or [self.env.company.id])
        self.sudo().create({
            'token_hash': _token_hash(raw_token),
            'user_id': self.env.uid,
            'company_id': self.env.company.id,
            'company_ids_json': json.dumps(company_ids),
            'model_name': model_name,
            'res_id': res_id,
            'record_ids': json.dumps(sorted({int(value) for value in (record_ids or [])})),
            'field_name': field_name,
            'attachment_id': attachment.id if attachment else False,
            'report_id': report.id if report else False,
            'name': name,
            'mimetype': mimetype or 'application/octet-stream',
            'payload': payload,
            'expires_at': expires_at,
        })
        return {
            'uri': 'nextosp://binary/%s' % raw_token,
            'downloadUrl': '/mcp/download/%s' % raw_token,
            'name': name,
            'mimeType': 'application/json',
            'downloadMimeType': mimetype or 'application/octet-stream',
            'expires_at': fields.Datetime.to_string(expires_at),
        }

    @api.model
    @api.private
    def consume(self, token):
        token_record = self.sudo().search([('token_hash', '=', _token_hash(token or ''))], limit=1)
        if not token_record:
            raise ValidationError(_('The download token is invalid.'))
        self.env.cr.execute(
            'SELECT id FROM mcp_download_token WHERE id = %s FOR UPDATE',
            [token_record.id],
        )
        token_record.invalidate_recordset()
        now = fields.Datetime.now()
        if token_record.user_id.id != self.env.uid:
            raise AccessError(_('The download token belongs to a different user.'))
        if token_record.consumed_at:
            raise ValidationError(_('The download token has already been used.'))
        if token_record.expires_at <= now:
            raise ValidationError(_('The download token has expired.'))

        company_ids = json.loads(token_record.company_ids_json or '[]')
        company_ids = company_ids or [token_record.company_id.id]
        allowed_company_ids = set(self.env.user.company_ids.ids)
        if not company_ids or not set(company_ids) <= allowed_company_ids:
            raise AccessError(_('The download token company context is no longer available.'))
        source = self.with_context(allowed_company_ids=company_ids)
        payload = False
        if token_record.model_name:
            if token_record.model_name not in source.env:
                raise ValidationError(_('The download source model is no longer available.'))
            policy = source.env['mcp.policy']._effective_for_model(token_record.model_name)
            permission = 'allow_reports' if token_record.report_id else 'allow_attachments'
            if not policy[permission]:
                raise AccessError(_('The MCP policy no longer permits this download.'))
        if token_record.model_name and token_record.record_ids:
            record_ids = json.loads(token_record.record_ids)
            if record_ids:
                records = source.env[token_record.model_name].browse(record_ids).exists()
                if set(records.ids) != set(record_ids):
                    raise ValidationError(_('One or more source records no longer exist.'))
                records.check_access('read')
        if token_record.report_id:
            report = source.env['ir.actions.report'].browse(token_record.report_id.id).exists()
            if not report:
                raise ValidationError(_('The source report no longer exists.'))
            report.check_access('read')
            if report.group_ids and not (report.group_ids & source.env.user.all_group_ids):
                raise AccessError(_('The report is no longer available to this user.'))
        if token_record.attachment_id:
            attachment = source.env['ir.attachment'].browse(token_record.attachment_id.id).exists()
            if not attachment:
                raise ValidationError(_('The source attachment no longer exists.'))
            if (
                attachment.res_model != token_record.model_name
                or attachment.res_id != token_record.res_id
            ):
                raise ValidationError(_('The source attachment changed after the token was issued.'))
            attachment.check_access('read')
            payload = attachment.datas
        elif token_record.model_name and token_record.res_id and token_record.field_name:
            record = source.env[token_record.model_name].browse(token_record.res_id).exists()
            if not record:
                raise ValidationError(_('The source record no longer exists.'))
            record.check_access('read')
            field = record._fields.get(token_record.field_name)
            if (
                not field or field.type != 'binary'
                or not record._has_field_access(field, 'read')
                or token_record.field_name in policy['blocked_fields']
                or (
                    policy['allowed_fields']
                    and token_record.field_name not in policy['allowed_fields']
                )
            ):
                raise AccessError(_('The binary field is not accessible.'))
            payload = record[token_record.field_name]
        else:
            # Stored report/ad-hoc payloads are only materialized after all
            # current policy, company, source-record and report checks pass.
            payload = token_record.payload

        token_record.write({'consumed_at': now})
        return {
            'name': token_record.name,
            'mimeType': token_record.mimetype or 'application/octet-stream',
            'blob': payload.decode() if isinstance(payload, bytes) else (payload or ''),
        }

    @api.autovacuum
    def _gc_mcp_download_tokens(self):
        cutoff = fields.Datetime.now() - datetime.timedelta(days=1)
        self.sudo().search([
            '|', ('expires_at', '<', cutoff), ('consumed_at', '<', cutoff),
        ]).unlink()

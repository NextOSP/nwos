# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import datetime
import json

from nwos import api, fields, models, _


_KEY_PLACEHOLDER = 'YOUR_API_KEY'
_CLIENT_NAME = 'nextosp'


class ResUsersApikeys(models.Model):
    _inherit = 'res.users.apikeys'

    def action_mcp_revoke(self):
        """Revoke one of the current user's keys from the MCP connection screen."""
        self.ensure_one()
        # ``_remove`` already enforces that the key is the user's own (or system).
        self._remove()
        return self.env['mcp.connection.wizard']._reopen_fresh()


class McpConnectionWizard(models.TransientModel):
    """One-click helper: generate an API key and copy a ready-made client setup.

    This is the friendly front door to MCP.  There is nothing to configure per
    model -- enabling the gateway and pasting the key below is all that is
    required.  The generated key belongs to the current user, so the assistant
    can only ever do what that account is already allowed to do.
    """

    _name = 'mcp.connection.wizard'
    _description = 'MCP Connection Assistant'

    key_name = fields.Char(
        string='Key Label', default='Claude', required=True,
        help='A name to recognise this API key later, e.g. the client using it.',
    )
    expiration_date = fields.Datetime(
        string='Expires On', default=lambda self: self._default_expiration_date(),
        help='Leave empty for a key that never expires (administrators only).',
    )
    mcp_enabled = fields.Boolean(compute='_compute_mcp_enabled')
    endpoint_url = fields.Char(compute='_compute_connection')
    api_key = fields.Char(readonly=True)
    generated = fields.Boolean(readonly=True)
    cli_command = fields.Char(compute='_compute_connection')
    client_config = fields.Text(compute='_compute_connection')
    existing_key_ids = fields.Many2many(
        'res.users.apikeys', compute='_compute_existing_keys',
        string='Your API Keys',
    )

    def _compute_display_name(self):
        # The wizard has no name field; give the breadcrumb a stable title
        # instead of an empty one.
        for wizard in self:
            wizard.display_name = _('Connect to MCP')

    def _default_expiration_date(self):
        durations = [
            duration
            for duration in self.env.user.all_group_ids.mapped('api_key_duration')
            if duration
        ]
        max_days = min(max(durations), 365) if durations else 365
        if self.env.is_system():
            max_days = 365
        return fields.Datetime.now() + datetime.timedelta(days=max_days)

    def _compute_mcp_enabled(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param('mcp.enabled')
        for wizard in self:
            wizard.mcp_enabled = str(enabled).strip().lower() in ('true', '1')

    @api.depends('api_key')
    def _compute_existing_keys(self):
        # Read only the current user's own keys; the secret column is never read.
        keys = self.env['res.users.apikeys'].sudo().search(
            [('user_id', '=', self.env.uid)], order='create_date desc',
        )
        for wizard in self:
            wizard.existing_key_ids = keys

    @api.depends('api_key')
    def _compute_connection(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', ''
        ).rstrip('/')
        endpoint = '%s/mcp' % base_url if base_url else '/mcp'
        database = self.env.cr.dbname
        for wizard in self:
            key = wizard.api_key or _KEY_PLACEHOLDER
            wizard.endpoint_url = endpoint
            wizard.cli_command = (
                'claude mcp add --transport http %s %s '
                '--header "Authorization: Bearer %s" '
                '--header "X-NWOS-Database: %s"'
                % (_CLIENT_NAME, endpoint, key, database)
            )
            wizard.client_config = json.dumps({
                'mcpServers': {
                    _CLIENT_NAME: {
                        'type': 'http',
                        'url': endpoint,
                        'headers': {
                            'Authorization': 'Bearer %s' % key,
                            'X-NWOS-Database': database,
                        },
                    },
                },
            }, indent=2)

    @api.model
    def _reopen_fresh(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connect to MCP'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connect to MCP'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_enable_gateway(self):
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param('mcp.enabled', 'True')
        return self._reopen()

    def action_generate_key(self):
        self.ensure_one()
        if not self.mcp_enabled:
            self.env['ir.config_parameter'].sudo().set_param('mcp.enabled', 'True')
        # The key is generated for the current user, so its reach is bounded by
        # that account's own ORM permissions -- never wider.
        key = self.env['res.users.apikeys']._generate(
            'rpc', self.key_name or 'Claude', self.expiration_date,
        )
        self.write({'api_key': key, 'generated': True})
        return self._reopen()

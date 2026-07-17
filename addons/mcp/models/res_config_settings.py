# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mcp_enabled = fields.Boolean(
        string='Enable MCP Gateway', default=False,
        config_parameter='mcp.enabled',
    )
    mcp_endpoint_url = fields.Char(
        string='MCP Endpoint URL', compute='_compute_mcp_endpoint_url',
        help='Point your MCP client here and authenticate with a Bearer API key.',
    )

    @api.depends('mcp_enabled')
    def _compute_mcp_endpoint_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', ''
        ).rstrip('/')
        for settings in self:
            settings.mcp_endpoint_url = '%s/mcp' % base_url if base_url else '/mcp'
    mcp_allowed_origins = fields.Char(
        string='Allowed MCP Origins',
        config_parameter='mcp.allowed_origins',
        help='Comma-separated origins. Leave empty for non-browser clients only.',
    )
    mcp_max_request_bytes = fields.Integer(
        string='Maximum MCP Request Size', default=1_048_576,
        config_parameter='mcp.max_request_bytes',
    )
    mcp_max_response_bytes = fields.Integer(
        string='Maximum MCP Response Size', default=1_048_576,
        config_parameter='mcp.max_response_bytes',
    )
    mcp_max_batch_size = fields.Integer(
        string='Maximum MCP Batch Size', default=20,
        config_parameter='mcp.max_batch_size',
    )
    mcp_max_page_size = fields.Integer(
        string='Maximum MCP Page Size', default=100,
        config_parameter='mcp.max_page_size',
    )
    mcp_execution_timeout = fields.Integer(
        string='MCP Execution Timeout (seconds)', default=30,
        config_parameter='mcp.execution_timeout',
    )
    mcp_confirmation_ttl = fields.Integer(
        string='MCP Confirmation Lifetime (seconds)', default=300,
        config_parameter='mcp.confirmation_ttl',
    )
    mcp_download_ttl = fields.Integer(
        string='MCP Download Lifetime (seconds)', default=300,
        config_parameter='mcp.download_ttl',
    )
    mcp_audit_retention_days = fields.Integer(
        string='MCP Audit Retention (days)', default=90,
        config_parameter='mcp.audit_retention_days',
    )

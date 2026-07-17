# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, fields, models, _
from nwos.exceptions import AccessError, ValidationError
from nwos.service.model import get_public_method


_FORBIDDEN_WORKFLOW_METHODS = {
    'browse', 'check_access', 'check_access_rights', 'check_access_rule',
    'copy', 'copy_data', 'create', 'default_get', 'ensure_one', 'exists',
    'export_data', 'fetch', 'fields_get', 'filtered', 'filtered_domain',
    'flush_model', 'flush_recordset', 'get_metadata', 'has_access',
    'invalidate_model', 'invalidate_recordset', 'load', 'mapped', 'name_create',
    'read', 'read_group', 'search', 'search_count', 'search_fetch', 'search_read',
    'sorted', 'sudo', 'toggle_active', 'action_archive', 'action_unarchive',
    'unlink', 'update', 'web_read', 'web_save', 'with_company', 'with_context',
    'with_env', 'with_prefetch', 'with_user', 'write',
}


class McpPolicy(models.Model):
    """Administrator policy applied on top of the normal ORM security model.

    An absent policy deliberately means fully available: discovery, read, create,
    update, reports and attachments are all on by default, so no per-model setup
    is required to start using MCP.  Effective access is still governed by the
    permissions of the user whose API key is used -- this policy only ever
    narrows that account, never widens it.  Deletion is the single opt-in
    operation, because it is irreversible.
    """

    _name = 'mcp.policy'
    _description = 'MCP Model Policy'
    _order = 'model_name'

    name = fields.Char(compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        'ir.model', required=True, ondelete='cascade', index=True,
        domain=[('abstract', '=', False), ('transient', '=', False)],
    )
    model_name = fields.Char(
        string='Technical Model Name', related='model_id.model', store=True, index=True,
    )
    allow_discovery = fields.Boolean(default=True)
    allow_read = fields.Boolean(default=True)
    allow_create = fields.Boolean(default=True)
    allow_update = fields.Boolean(default=True)
    allow_delete = fields.Boolean(default=False)
    allow_reports = fields.Boolean(default=True)
    allow_attachments = fields.Boolean(default=True)
    allowed_field_ids = fields.Many2many(
        'ir.model.fields', 'mcp_policy_allowed_field_rel',
        'policy_id', 'field_id', string='Allowed Fields',
    )
    blocked_field_ids = fields.Many2many(
        'ir.model.fields', 'mcp_policy_blocked_field_rel',
        'policy_id', 'field_id', string='Blocked Fields',
    )
    workflow_methods = fields.Text(
        help='One public model method per line. Lines starting with # are ignored.',
    )
    max_results = fields.Integer(default=100, required=True)

    _model_unique = models.Constraint(
        'UNIQUE (model_id)',
        'Only one MCP policy can be configured for a model.',
    )
    _max_results_positive = models.Constraint(
        'CHECK (max_results > 0)',
        'The maximum result count must be strictly positive.',
    )

    @api.depends('model_id', 'model_id.name')
    def _compute_name(self):
        for policy in self:
            policy.name = policy.model_id.name or policy.model_id.model

    @api.constrains('allowed_field_ids', 'blocked_field_ids', 'model_id')
    def _check_fields_belong_to_model(self):
        for policy in self:
            invalid = (policy.allowed_field_ids | policy.blocked_field_ids).filtered(
                lambda field: field.model_id != policy.model_id
            )
            if invalid:
                raise ValidationError(_(
                    'Every allowed or blocked MCP field must belong to the policy model.'
                ))

    @api.constrains('workflow_methods')
    def _check_workflow_methods(self):
        for policy in self:
            methods = {
                line.strip()
                for line in (policy.workflow_methods or '').splitlines()
                if line.strip() and not line.lstrip().startswith('#')
            }
            invalid = {
                method for method in methods
                if not method.isidentifier() or method.startswith('_')
                or method in _FORBIDDEN_WORKFLOW_METHODS
            }
            model = self.env.get(policy.model_name) if policy.model_name else None
            if model:
                for method_name in methods - invalid:
                    try:
                        method = get_public_method(model, method_name)
                    except (AccessError, AttributeError):
                        invalid.add(method_name)
                    else:
                        if getattr(method, '_api_model', False):
                            invalid.add(method_name)
            if invalid:
                raise ValidationError(_(
                    'These methods cannot be exposed as MCP workflows: %s',
                    ', '.join(sorted(invalid)),
                ))

    @api.model
    def _default_effective_policy(self):
        return {
            'configured': False,
            'allow_discovery': True,
            'allow_read': True,
            'allow_create': True,
            'allow_update': True,
            'allow_delete': False,
            'allow_reports': True,
            'allow_attachments': True,
            'allowed_fields': set(),
            'blocked_fields': set(),
            'workflow_methods': set(),
            'max_results': 100,
        }

    def _effective_values(self):
        self.ensure_one()
        methods = {
            line.strip()
            for line in (self.workflow_methods or '').splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        }
        values = {
            'configured': True,
            'allow_discovery': self.allow_discovery,
            'allow_read': self.allow_read,
            'allow_create': self.allow_create,
            'allow_update': self.allow_update,
            'allow_delete': self.allow_delete,
            'allow_reports': self.allow_reports,
            'allow_attachments': self.allow_attachments,
            'allowed_fields': set(self.allowed_field_ids.mapped('name')),
            'blocked_fields': set(self.blocked_field_ids.mapped('name')),
            'workflow_methods': methods,
            'max_results': self.max_results,
        }
        if not self.active:
            # An archived security policy remains an explicit fail-closed
            # decision; deleting it is what restores the default access.
            for permission in (
                'allow_discovery', 'allow_read', 'allow_create', 'allow_update',
                'allow_delete', 'allow_reports', 'allow_attachments',
            ):
                values[permission] = False
            values['workflow_methods'] = set()
        return values

    @api.model
    def _effective_for_model(self, model_name):
        """Return policy metadata without elevating any business records."""
        policy = self.with_context(active_test=False).sudo().search([
            ('model_name', '=', model_name),
        ], limit=1)
        return policy._effective_values() if policy else self._default_effective_policy()

    @api.model
    def _effective_policy_map(self):
        policies = self.with_context(active_test=False).sudo().search([])
        return {
            policy.model_name: policy._effective_values()
            for policy in policies
        }

# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import functools
import logging

from nwos import _, api, fields, models
from nwos.exceptions import UserError, ValidationError
from nwos.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

#: Context key holding a tuple of "model.method" entries that already cleared
#: approval. Only the exact gated method on the exact model is bypassed, so a
#: nested gate on another model still fires.
BYPASS_KEY = 'approval_bypass'

#: Methods that may never be gated: gating CRUD would break the ORM itself.
METHOD_BLACKLIST = {
    'create', 'write', 'unlink', 'read', 'copy', 'browse', 'search',
    'search_read', 'web_save', 'web_read', 'onchange', 'default_get',
    'fields_get', 'name_create', 'load', 'export_data',
}

APPROVER_TYPE_SELECTION = [
    ('group', 'Security Group'),
    ('users', 'Specific Users'),
    ('manager', 'Requester Manager (org chart)'),
    ('department_manager', 'Department Manager'),
    ('field', 'Field on the Document'),
]

APPROVAL_MODE_SELECTION = [
    ('any', 'Any one approves'),
    ('all', 'Everyone must approve'),
]


def _company_of(record):
    """The company a document belongs to, or an empty recordset."""
    if 'company_id' in record._fields:
        return record.sudo().company_id
    return record.env['res.company'].browse()


def _make_gate(method_name):
    """Build the wrapper installed over ``method_name`` on a target model.

    Defined in its own function so the closure binds this call's
    ``method_name`` (the same reason base_automation builds its patches in
    ``make_create()``-style factories).
    """
    def gate(self, *args, **kwargs):
        if f'{self._name}.{method_name}' in (self.env.context.get(BYPASS_KEY) or ()):
            return gate.origin(self, *args, **kwargs)
        Request = self.env['approval.request'].sudo()
        allowed = self.browse()
        blocked = self.browse()
        for record in self:
            if Request._gate_record(record, method_name, kwargs) == 'proceed':
                allowed |= record
            else:
                blocked |= record
        if not allowed:
            return Request._blocked_notification(blocked)
        result = gate.origin(allowed.with_env(self.env), *args, **kwargs)
        if blocked:
            return Request._blocked_notification(blocked, result)
        return result

    return gate


class ApprovalRule(models.Model):
    _name = 'approval.rule'
    _description = 'Approval Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(
        default=10, help="Rules are evaluated in this order; the first match wins.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        help="Leave empty to apply to every company.")

    # --- what is gated ---------------------------------------------------
    res_model_id = fields.Many2one(
        'ir.model', string='Document Model', required=True, ondelete='cascade',
        help="The model whose action requires approval.")
    res_model = fields.Char(
        related='res_model_id.model', string='Model Name', store=True, index=True)
    method_name = fields.Char(
        string='Approved Action', required=True,
        help="Technical name of the button/method that requires approval, "
             "e.g. action_confirm, button_confirm, action_send.")
    method_hint = fields.Text(
        string='Available Actions', compute='_compute_method_hint')
    reject_method_name = fields.Char(
        string='On Reject, Call',
        help="Optional method called on the document when the approval is "
             "rejected. It receives the reason in the context key "
             "'approval_reject_reason'.")
    block_mode = fields.Selection([
        ('soft', 'Notify the user'),
        ('raise', 'Raise an error'),
    ], required=True, default='soft', string='When Blocked',
        help="How to react when the action is blocked. 'Raise an error' is "
             "meant for methods called programmatically, where a silent "
             "no-op would be dangerous.")

    # --- when it applies -------------------------------------------------
    condition_domain = fields.Char(
        string='Applies To', default='[]',
        help="Only documents matching this filter require approval.")
    amount_field_id = fields.Many2one(
        'ir.model.fields', string='Amount Field', ondelete='cascade',
        domain="[('model_id', '=', res_model_id), "
               "('ttype', 'in', ('monetary', 'float')), ('store', '=', True)]")
    currency_field_id = fields.Many2one(
        'ir.model.fields', string='Currency Field', ondelete='cascade',
        domain="[('model_id', '=', res_model_id), ('ttype', '=', 'many2one'), "
               "('relation', '=', 'res.currency')]")
    amount_min = fields.Float(string='Amount ≥')
    amount_max = fields.Float(
        string='Amount <', help="0 means no upper limit.")

    # --- how the document is read ----------------------------------------
    requester_field_id = fields.Many2one(
        'ir.model.fields', string='Requester Field', ondelete='cascade',
        domain="[('model_id', '=', res_model_id), ('ttype', '=', 'many2one'), "
               "('relation', 'in', ('res.users', 'hr.employee'))]",
        help="Who is asking for approval. Defaults to the document's creator.")
    department_field_id = fields.Many2one(
        'ir.model.fields', string='Department Field', ondelete='cascade',
        domain="[('model_id', '=', res_model_id), ('ttype', '=', 'many2one'), "
               "('relation', '=', 'hr.department')]",
        help="Used by the 'Department Manager' approver type. Defaults to the "
             "requester's own department.")

    # --- who approves -----------------------------------------------------
    step_ids = fields.One2many(
        'approval.rule.step', 'rule_id', string='Approval Steps', copy=True)
    auto_ids = fields.One2many(
        'approval.rule.auto', 'rule_id', string='Auto-Approval', copy=True)
    override_group_id = fields.Many2one(
        'res.groups', string='Override Group',
        default=lambda self: self.env.ref(
            'nwos_approval.group_approval_manager', raise_if_not_found=False),
        help="Members of this group may approve any step of this flow.")
    mail_template_id = fields.Many2one(
        'mail.template', string='Approval Email',
        domain="[('model_id', '=', res_model_id)]",
        help="Sent on the document once every step is approved.")

    _sql_constraints = [
        ('amount_window', 'CHECK (amount_max = 0 OR amount_max > amount_min)',
         'The upper amount must be greater than the lower amount.'),
    ]

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @api.depends('res_model')
    def _compute_method_hint(self):
        for rule in self:
            methods = rule._get_gateable_methods()
            rule.method_hint = ", ".join(methods) if methods else False

    def _get_gateable_methods(self):
        """Public action-like methods that may be gated on the target model."""
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env:
            return []
        cls = type(self.env[self.res_model])
        names = set()
        for name in dir(cls):
            if not name.startswith(('action_', 'button_')):
                continue
            method = getattr(cls, name, None)
            if not callable(method) or getattr(method, '_api_model', False):
                continue
            names.add(name)
        return sorted(names)

    @api.onchange('res_model_id')
    def _onchange_res_model_id(self):
        """Clear model-dependent config and suggest the most likely button."""
        self.amount_field_id = False
        self.currency_field_id = False
        self.requester_field_id = False
        self.department_field_id = False
        self.mail_template_id = False
        self.condition_domain = '[]'
        available = self._get_gateable_methods()
        if self.method_name not in available:
            self.method_name = next(
                (candidate for candidate in
                 ('action_confirm', 'button_confirm', 'action_send',
                  'action_submit', 'action_validate', 'action_post')
                 if candidate in available), False)

    @api.constrains('res_model_id', 'method_name')
    def _check_method_name(self):
        for rule in self:
            model = self.env.get(rule.res_model)
            if model is None:
                raise ValidationError(_(
                    "The model %s is not available.", rule.res_model))
            name = (rule.method_name or '').strip()
            if name.startswith('_') or name in METHOD_BLACKLIST:
                raise ValidationError(_(
                    "'%s' cannot be gated. Choose a public action method such "
                    "as action_confirm.", name))
            method = getattr(type(model), name, None)
            if not callable(method):
                raise ValidationError(_(
                    "%(model)s has no method '%(method)s'. Available actions: "
                    "%(available)s",
                    model=rule.res_model, method=name,
                    available=", ".join(rule._get_gateable_methods()) or _("none")))
            if getattr(method, '_api_model', False):
                raise ValidationError(_(
                    "'%s' works on the model rather than on records, so there "
                    "is no document to approve.", name))

    @api.constrains('reject_method_name', 'res_model_id')
    def _check_reject_method_name(self):
        for rule in self:
            if not rule.reject_method_name:
                continue
            model = self.env.get(rule.res_model)
            if model is None or not callable(
                    getattr(type(model), rule.reject_method_name, None)):
                raise ValidationError(_(
                    "%(model)s has no method '%(method)s'.",
                    model=rule.res_model, method=rule.reject_method_name))

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def _match(self, record, method_name):
        """Return the first rule that applies to ``record.method_name``."""
        domain = [('res_model', '=', record._name),
                  ('method_name', '=', method_name)]
        company = _company_of(record)
        if company:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', company.id)]
        for rule in self.sudo().search(domain, order='sequence, id'):
            if rule._matches(record):
                return rule
        return self.browse()

    def _matches(self, record):
        self.ensure_one()
        company = _company_of(record)
        if self.company_id and company and self.company_id != company:
            return False
        if self.condition_domain and self.condition_domain != '[]':
            try:
                domain = safe_eval(self.condition_domain,
                                   {'user': self.env.user, 'uid': self.env.uid})
            except Exception:
                _logger.exception(
                    "approval.rule %s: invalid domain %r", self.id,
                    self.condition_domain)
                return False
            if not record.sudo().filtered_domain(domain):
                return False
        if self.amount_min or self.amount_max:
            amount = self._get_amount(record)
            if amount < self.amount_min:
                return False
            if self.amount_max and amount >= self.amount_max:
                return False
        return True

    def _get_amount(self, record):
        self.ensure_one()
        field_name = self.amount_field_id.name
        if not field_name or field_name not in record._fields:
            return 0.0
        return record.sudo()[field_name] or 0.0

    def _get_currency(self, record):
        self.ensure_one()
        field_name = self.currency_field_id.name
        if field_name and field_name in record._fields:
            return record.sudo()[field_name]
        if 'currency_id' in record._fields:
            return record.sudo().currency_id
        company = _company_of(record) or self.env.company
        return company.currency_id

    def _get_requester(self, record):
        """The user asking for approval: configured field, else the creator."""
        self.ensure_one()
        field_name = self.requester_field_id.name
        if field_name and field_name in record._fields:
            value = record.sudo()[field_name]
            if value._name == 'res.users':
                return value
            if value._name == 'hr.employee' and value.user_id:
                return value.user_id
        return record.sudo().create_uid or self.env.user

    def _get_department(self, record):
        self.ensure_one()
        field_name = self.department_field_id.name
        if field_name and field_name in record._fields:
            department = record.sudo()[field_name]
            if department:
                return department
        requester = self._get_requester(record)
        return requester.employee_id.department_id

    # ------------------------------------------------------------------
    # Registry patching
    # ------------------------------------------------------------------
    def _register_hook(self):
        """Install the approval gate on every configured model/method."""
        patched = self.env.registry.__dict__.setdefault(
            '_nwos_approval_patched', set())
        for rule in self.sudo().with_context(active_test=True).search([]):
            key = (rule.res_model, rule.method_name)
            if key in patched:
                continue
            Model = self.env.get(rule.res_model)
            if Model is None:
                _logger.warning(
                    "Approval rule %r (#%s) targets missing model %s",
                    rule.name, rule.id, rule.res_model)
                continue
            ModelClass = self.env.registry[rule.res_model]
            origin = getattr(ModelClass, rule.method_name, None)
            if not callable(origin):
                _logger.warning(
                    "Approval rule %r (#%s): %s has no method %s",
                    rule.name, rule.id, rule.res_model, rule.method_name)
                continue
            gate = _make_gate(rule.method_name)
            functools.update_wrapper(gate, origin)
            gate.origin = origin
            gate._nwos_approval_gate = True
            setattr(ModelClass, rule.method_name, gate)
            patched.add(key)

    def _unregister_hook(self):
        """Remove only the patches this module installed."""
        patched = self.env.registry.__dict__.pop('_nwos_approval_patched', set())
        for model_name, method_name in patched:
            ModelClass = self.env.registry.get(model_name)
            if ModelClass is None:
                continue
            current = ModelClass.__dict__.get(method_name)
            if getattr(current, '_nwos_approval_gate', False):
                delattr(ModelClass, method_name)

    def _update_registry(self):
        """Re-install the patches here and notify the other workers."""
        if self.env.registry.ready and not self.env.context.get('import_file'):
            self._unregister_hook()
            self._register_hook()
            self.env.registry.registry_invalidated = True

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._update_registry()
        return rules

    def write(self, vals):
        result = super().write(vals)
        if {'res_model_id', 'method_name', 'active'} & set(vals):
            self._update_registry()
        return result

    def unlink(self):
        result = super().unlink()
        self._update_registry()
        return result


class ApprovalRuleStep(models.Model):
    _name = 'approval.rule.step'
    _description = 'Approval Rule Step'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'approval.rule', required=True, ondelete='cascade')
    res_model_id = fields.Many2one(
        related='rule_id.res_model_id', string='Document Model')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True)
    approver_type = fields.Selection(
        APPROVER_TYPE_SELECTION, string='Approvers', required=True,
        default='group')
    user_ids = fields.Many2many('res.users', string='Specific Users')
    group_id = fields.Many2one('res.groups', string='Group')
    approver_field_id = fields.Many2one(
        'ir.model.fields', string='User Field', ondelete='cascade',
        domain="[('model_id', '=', res_model_id), "
               "('ttype', 'in', ('many2one', 'many2many')), "
               "('relation', 'in', ('res.users', 'hr.employee'))]",
        help="Approvers are read from this field of the document itself, "
             "e.g. the salesperson of the order.")
    manager_level = fields.Integer(
        string='Levels Up', default=1,
        help="For the org-chart approver: how many manager levels above the "
             "requester.")
    approval_mode = fields.Selection(
        APPROVAL_MODE_SELECTION, string='Mode', required=True, default='any')

    def _resolve_approvers(self, record):
        """Return the res.users allowed to approve this step for a document."""
        self.ensure_one()
        Users = self.env['res.users']
        rule = self.rule_id
        if self.approver_type == 'users':
            return self.user_ids
        if self.approver_type == 'group':
            return self.group_id.all_user_ids
        if self.approver_type == 'field':
            field_name = self.approver_field_id.name
            if not field_name or field_name not in record._fields:
                return Users
            value = record.sudo()[field_name]
            if value._name == 'hr.employee':
                return value.user_id
            return value
        if self.approver_type == 'manager':
            employee = rule._get_requester(record).employee_id
            for _level in range(max(self.manager_level, 1)):
                employee = employee.parent_id
                if not employee:
                    break
            return employee.user_id if employee else Users
        if self.approver_type == 'department_manager':
            return rule._get_department(record).manager_id.user_id
        return Users


class ApprovalRuleAuto(models.Model):
    _name = 'approval.rule.auto'
    _description = 'Approval Auto-Approval Line'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'approval.rule', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, default='Auto-approval')
    user_ids = fields.Many2many(
        'res.users', string='Requesters',
        help="Applies to these requesters only. Empty means everyone.")
    max_amount = fields.Float(
        string='Amount <', required=True,
        help="Auto-approve when the document amount is below this.")
    scope = fields.Selection([
        ('all', 'All steps (fully auto-approved)'),
        ('first', 'First step only'),
    ], required=True, default='all')

    def _matches(self, record, requester, amount):
        self.ensure_one()
        if amount >= self.max_amount:
            return False
        if self.user_ids and requester not in self.user_ids:
            return False
        return True

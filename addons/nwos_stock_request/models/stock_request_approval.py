# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import _, api, fields, models
from nwos.exceptions import UserError

PURPOSE_SELECTION = [
    ('stock', 'Replenish Stock'),
    ('office', 'Office / Consumable'),
    ('project', 'Project'),
    ('manufacture', 'Manufacturing'),
]

APPROVER_TYPE_SELECTION = [
    ('manager', 'Requester Manager (org chart)'),
    ('department_manager', 'Department Manager'),
    ('users', 'Specific Users'),
    ('group', 'Security Group'),
]

APPROVAL_MODE_SELECTION = [
    ('any', 'Any one approves'),
    ('all', 'Everyone must approve'),
]


class StockRequestApprovalRule(models.Model):
    _name = 'stock.request.approval.rule'
    _description = 'Stock Request Approval Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(
        default=10, help="Rules are evaluated in this order; the first match wins.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    # --- matching conditions ---
    min_amount = fields.Monetary(
        string='Amount ≥', help="Applies when the estimated total is at least this.")
    max_amount = fields.Monetary(
        string='Amount <',
        help="Applies when the estimated total is below this. 0 = no upper limit.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    purpose = fields.Selection(
        PURPOSE_SELECTION, string='Purpose',
        help="Leave empty to match any purpose.")
    warehouse_ids = fields.Many2many(
        'stock.warehouse', string='Warehouses',
        help="Leave empty to match any warehouse.")
    department_ids = fields.Many2many(
        'hr.department', string='Departments',
        help="Leave empty to match any department.")

    step_ids = fields.One2many(
        'stock.request.approval.rule.step', 'rule_id', string='Approval Steps', copy=True)

    def _matches(self, request):
        self.ensure_one()
        amount = request.estimated_total
        if self.company_id != request.company_id:
            return False
        if amount < self.min_amount:
            return False
        if self.max_amount and amount >= self.max_amount:
            return False
        if self.purpose and self.purpose != request.purpose:
            return False
        if self.warehouse_ids and request.warehouse_id not in self.warehouse_ids:
            return False
        if self.department_ids and request.department_id not in self.department_ids:
            return False
        return True


class StockRequestApprovalRuleStep(models.Model):
    _name = 'stock.request.approval.rule.step'
    _description = 'Stock Request Approval Rule Step'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'stock.request.approval.rule', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True)
    approver_type = fields.Selection(
        APPROVER_TYPE_SELECTION, string='Approver', required=True, default='group')
    user_ids = fields.Many2many('res.users', string='Specific Users')
    group_id = fields.Many2one('res.groups', string='Group')
    manager_level = fields.Integer(
        string='Levels Up', default=1,
        help="For the org-chart approver: how many manager levels above the requester.")
    approval_mode = fields.Selection(
        APPROVAL_MODE_SELECTION, string='Mode', required=True, default='any')

    def _resolve_approvers(self, request):
        """Return the res.users that may approve this step for a given request."""
        self.ensure_one()
        Users = request.env['res.users']
        if self.approver_type == 'users':
            return self.user_ids
        if self.approver_type == 'group':
            return self.group_id.all_user_ids
        if self.approver_type == 'manager':
            employee = request.requester_id.employee_id
            for _i in range(max(self.manager_level, 1)):
                employee = employee.parent_id
                if not employee:
                    break
            return employee.user_id if employee else Users
        if self.approver_type == 'department_manager':
            department = request.department_id or \
                request.requester_id.employee_id.department_id
            return department.manager_id.user_id
        return Users


class StockRequestApprovalAuto(models.Model):
    _name = 'stock.request.approval.auto'
    _description = 'Stock Request Auto-Approval'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    user_ids = fields.Many2many(
        'res.users', string='Users',
        help="Requesters this auto-approval applies to. Empty = all users.")
    max_amount = fields.Monetary(
        string='Amount <', required=True,
        help="Auto-approve when the estimated total is below this amount.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    scope = fields.Selection([
        ('first', 'First step only'),
        ('all', 'All steps (fully auto-approved)'),
    ], string='Scope', required=True, default='all',
        help="Auto-approve only the first step, or the whole request.")

    def _matches(self, request):
        self.ensure_one()
        if self.company_id != request.company_id:
            return False
        if request.estimated_total >= self.max_amount:
            return False
        if self.user_ids and request.requester_id not in self.user_ids:
            return False
        return True


class StockRequestApproval(models.Model):
    _name = 'stock.request.approval'
    _description = 'Stock Request Approval Step'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'stock.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='request_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True)
    approval_mode = fields.Selection(
        APPROVAL_MODE_SELECTION, required=True, default='any')
    approver_ids = fields.Many2many(
        'res.users', 'stock_request_approval_candidate_rel',
        'approval_id', 'user_id', string='Approvers')
    approved_user_ids = fields.Many2many(
        'res.users', 'stock_request_approval_done_rel',
        'approval_id', 'user_id', string='Approved By', copy=False)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True, copy=False, index=True)
    reject_reason = fields.Char(copy=False)
    is_current = fields.Boolean(compute='_compute_is_current')
    can_approve = fields.Boolean(compute='_compute_can_approve')
    approver_names = fields.Char(compute='_compute_approver_names')

    @api.depends('request_id.approval_ids.status', 'sequence', 'status')
    def _compute_is_current(self):
        for approval in self:
            pending = approval.request_id.approval_ids.filtered(
                lambda a: a.status == 'pending').sorted('sequence')
            approval.is_current = bool(pending) and pending[0] == approval

    @api.depends_context('uid')
    @api.depends('request_id.approval_ids.status', 'sequence', 'status',
                 'approver_ids', 'approved_user_ids')
    def _compute_can_approve(self):
        for approval in self:
            approval.can_approve = approval._user_can_approve()

    def _user_can_approve(self):
        """Fresh (non-cached) check: may the current user approve this step now."""
        self.ensure_one()
        if self.status != 'pending':
            return False
        pending = self.request_id.approval_ids.filtered(
            lambda a: a.status == 'pending').sorted('sequence')
        if not pending or pending[0].id != self.id:
            return False
        user = self.env.user
        if user in self.approved_user_ids:
            return False
        return (user in self.approver_ids
                or user.has_group('nwos_stock_request.group_stock_request_manager'))

    @api.depends('approver_ids')
    def _compute_approver_names(self):
        for approval in self:
            approval.approver_names = ", ".join(
                approval.approver_ids.mapped('name')) or _("(no approver resolved)")

    def _is_satisfied(self):
        self.ensure_one()
        if self.approval_mode == 'all':
            return bool(self.approver_ids) and \
                all(u in self.approved_user_ids for u in self.approver_ids)
        return bool(self.approved_user_ids)

    def action_approve_step(self):
        for approval in self:
            if not approval._user_can_approve():
                raise UserError(_(
                    "You cannot approve this step (not an approver, or not the "
                    "current step)."))
            approval.approved_user_ids = [(4, self.env.user.id)]
            if approval._is_satisfied():
                approval.status = 'approved'
            approval.request_id.message_post(
                body=_("%(user)s approved step '%(step)s'.",
                       user=self.env.user.name, step=approval.name))
            approval.request_id._recompute_approval_state()
        return True

    def action_reject_step(self):
        return {
            'name': _('Reject'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.request.refuse',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.request_id.id,
                        'default_approval_id': self.id},
        }

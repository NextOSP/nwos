# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import json
import logging
import traceback

from nwos import _, api, fields, models
from nwos.exceptions import UserError

from .approval_rule import APPROVAL_MODE_SELECTION, BYPASS_KEY, _company_of

_logger = logging.getLogger(__name__)

STATE_SELECTION = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('done', 'Done'),
    ('rejected', 'Rejected'),
    ('error', 'Failed'),
    ('cancel', 'Cancelled'),
]


class ApprovalRequest(models.Model):
    _name = 'approval.request'
    _description = 'Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='/')
    rule_id = fields.Many2one('approval.rule', string='Rule', ondelete='set null')
    company_id = fields.Many2one('res.company', string='Company', index=True)

    res_model = fields.Char(string='Document Model', required=True, index=True)
    res_model_name = fields.Char(
        string='Document Type', compute='_compute_res_model_name', store=True)
    res_id = fields.Many2oneReference(
        string='Document', model_field='res_model', required=True, index=True)
    res_name = fields.Char(string='Document Reference', index=True)

    method_name = fields.Char(required=True)
    method_kwargs = fields.Json(default=dict)

    requester_id = fields.Many2one('res.users', string='Requested by', index=True)
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')
    override_group_id = fields.Many2one('res.groups', string='Override Group')

    state = fields.Selection(
        STATE_SELECTION, required=True, default='pending', index=True,
        copy=False, tracking=True)
    step_ids = fields.One2many('approval.step', 'request_id', string='Steps')
    current_step_id = fields.Many2one(
        'approval.step', compute='_compute_current_step')
    can_approve = fields.Boolean(compute='_compute_current_step')
    pending_approver_ids = fields.Many2many(
        'res.users', string='Pending Approvers',
        compute='_compute_pending_approvers', store=True)

    date_submitted = fields.Datetime(default=fields.Datetime.now, readonly=True)
    date_resolved = fields.Datetime(readonly=True, copy=False)
    approver_id = fields.Many2one('res.users', string='Last Approver', readonly=True)
    reject_reason = fields.Char(readonly=True, copy=False)
    error_trace = fields.Text(readonly=True, copy=False)

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS approval_request_document_state_idx
            ON approval_request (res_model, res_id, state)
        """)

    # ------------------------------------------------------------------
    # Compute / defaults
    # ------------------------------------------------------------------
    @api.depends('res_model')
    def _compute_res_model_name(self):
        models_data = self.env['ir.model'].sudo().search_read(
            [('model', 'in', list(set(self.mapped('res_model'))))],
            ['model', 'name'], load=False)
        names = {entry['model']: entry['name'] for entry in models_data}
        for request in self:
            request.res_model_name = names.get(request.res_model, request.res_model)

    @api.depends_context('uid')
    @api.depends('step_ids.status', 'step_ids.sequence', 'state')
    def _compute_current_step(self):
        for request in self:
            pending = request.step_ids.filtered(
                lambda s: s.status == 'pending').sorted('sequence')
            current = pending[0] if pending else request.env['approval.step']
            request.current_step_id = current
            request.can_approve = (
                request.state == 'pending' and bool(current)
                and current._user_can_approve())

    @api.depends('step_ids.status', 'step_ids.approver_ids', 'state')
    def _compute_pending_approvers(self):
        for request in self:
            pending = request.step_ids.filtered(
                lambda s: s.status == 'pending').sorted('sequence')
            request.pending_approver_ids = (
                pending[0].approver_ids if pending and request.state == 'pending'
                else [(5, 0, 0)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'approval.request') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Gate entry point
    # ------------------------------------------------------------------
    @api.model
    def _gate_record(self, record, method_name, kwargs=None):
        """Decide whether ``record.method_name()`` may run now.

        Returns ``'proceed'`` or ``'blocked'``. Never raises for the soft
        block mode: the caller turns a block into a notification, because
        raising would roll back the approval rows we just created.
        """
        existing = self.sudo().search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('method_name', '=', method_name),
            ('state', 'in', ('pending', 'approved')),
        ], order='id desc', limit=1)
        if existing:
            if existing.state == 'approved':
                # Safety net: the automatic resume did not run (or failed) and
                # the user clicked the button again. Consume the approval.
                existing._mark_done()
                return 'proceed'
            return 'blocked'

        rule = self.env['approval.rule']._match(record, method_name)
        if not rule:
            return 'proceed'

        if rule.block_mode == 'raise':
            self._create_request_isolated(record, method_name, rule, kwargs)
            raise UserError(_(
                "%(document)s needs approval before '%(action)s' can run. "
                "An approval request has been created.",
                document=record.display_name, action=method_name))

        request = self._request_approval(record, method_name, rule, kwargs)
        if request.state == 'approved':
            # Fully auto-approved: let the original call go through right now
            # instead of re-entering it from _on_fully_approved.
            request._mark_done()
            return 'proceed'
        return 'blocked'

    @api.model
    def _create_request_isolated(self, record, method_name, rule, kwargs):
        """Create the request in its own cursor, so a later raise keeps it."""
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            env['approval.request'].sudo()._request_approval(
                record.with_env(env), method_name, rule.with_env(env), kwargs)
            cr.commit()

    @api.model
    def _request_approval(self, record, method_name, rule, kwargs=None):
        """Create the approval request and its steps for a document."""
        requester = rule._get_requester(record)
        amount = rule._get_amount(record)
        request = self.sudo().create({
            'rule_id': rule.id,
            'company_id': (_company_of(record) or self.env.company).id,
            'res_model': record._name,
            'res_id': record.id,
            'res_name': record.display_name,
            'method_name': method_name,
            'method_kwargs': self._serialisable_kwargs(kwargs),
            'requester_id': requester.id,
            'amount': amount,
            'currency_id': rule._get_currency(record).id,
            'override_group_id': rule.override_group_id.id,
        })
        request._generate_steps(record, rule)
        request._apply_auto_approval(requester, amount)
        request._recompute_state(resume=False)
        request._post_to_document(_(
            "Approval requested for '%(action)s' — %(request)s.",
            action=method_name, request=request.name))
        return request

    @api.model
    def _serialisable_kwargs(self, kwargs):
        if not kwargs:
            return {}
        try:
            json.dumps(kwargs)
        except TypeError:
            _logger.info(
                "Approval: dropping non-serialisable kwargs %s", list(kwargs))
            return {}
        return kwargs

    def _generate_steps(self, record, rule):
        self.ensure_one()
        Step = self.env['approval.step'].sudo()
        self.step_ids.unlink()
        for step in rule.step_ids:
            approvers = step._resolve_approvers(record)
            Step.create({
                'request_id': self.id,
                'sequence': step.sequence,
                'name': step.name,
                'approval_mode': step.approval_mode,
                'approver_ids': [(6, 0, approvers.ids)],
            })
        if not self.step_ids:
            Step.create({
                'request_id': self.id,
                'sequence': 10,
                'name': _("Approval"),
                'approval_mode': 'any',
                'approver_ids': [(6, 0, rule.override_group_id.all_user_ids.ids)],
            })

    def _apply_auto_approval(self, requester, amount):
        self.ensure_one()
        scope = None
        for auto in self.rule_id.auto_ids.sorted('sequence'):
            if auto._matches(self.record_ref(), requester, amount):
                scope = auto.scope
                break
        if scope is None:
            return
        steps = self.step_ids.sorted('sequence')
        for step in (steps if scope == 'all' else steps[:1]):
            step.write({
                'status': 'approved',
                'approved_user_ids': [(4, requester.id)],
            })
        self.sudo().message_post(body=_("Auto-approved (%s).", scope))

    # ------------------------------------------------------------------
    # Advancing the flow
    # ------------------------------------------------------------------
    def _recompute_state(self, resume=True):
        """Move the request forward when every step is approved."""
        self.ensure_one()
        if self.state != 'pending':
            return
        if self.step_ids and all(s.status == 'approved' for s in self.step_ids):
            self.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'date_resolved': fields.Datetime.now(),
            })
            self._clear_activities()
            if resume:
                self._on_fully_approved()
        else:
            self._schedule_current_activity()

    def _on_fully_approved(self):
        """Re-run the blocked method, as the requester, bypassing the gate."""
        self.ensure_one()
        record = self.record_ref()
        if not record:
            self._mark_done()
            return
        user = self.requester_id or self.env.user
        context = dict(self.env.context)
        context[BYPASS_KEY] = tuple(context.get(BYPASS_KEY) or ()) + (
            f'{self.res_model}.{self.method_name}',)
        context['approval_request_id'] = self.id
        try:
            # A savepoint, not a rollback: undoing the failed action must not
            # take the approval rows with it.
            with self.env.cr.savepoint():
                method = getattr(
                    record.with_user(user).with_context(**context),
                    self.method_name)
                method(**(self.method_kwargs or {}))
        except Exception:
            self.sudo().write({
                'state': 'error',
                'error_trace': traceback.format_exc(),
            })
            self._post_to_document(_(
                "Approved, but running '%(action)s' failed. See approval "
                "request %(request)s.",
                action=self.method_name, request=self.name))
            _logger.exception(
                "Approval %s: resuming %s.%s failed",
                self.name, self.res_model, self.method_name)
        else:
            self._mark_done()
            self._send_approval_mail()

    def _mark_done(self):
        self.ensure_one()
        self.sudo().write({
            'state': 'done',
            'date_resolved': self.date_resolved or fields.Datetime.now(),
        })

    def action_retry(self):
        """Re-run a resume that previously failed."""
        for request in self:
            if request.state != 'error':
                raise UserError(_("Only failed approvals can be retried."))
            request.sudo().write({'state': 'approved', 'error_trace': False})
            request._on_fully_approved()
        return True

    def _send_approval_mail(self):
        self.ensure_one()
        template = self.rule_id.mail_template_id
        record = self.record_ref()
        if template and record:
            template.send_mail(record.id, force_send=False)

    def _reject(self, reason, step=None):
        """Reject the whole request, optionally marking the failing step."""
        self.ensure_one()
        if step:
            step.sudo().write({'status': 'rejected', 'reject_reason': reason})
        self.sudo().write({
            'state': 'rejected',
            'reject_reason': reason,
            'approver_id': self.env.user.id,
            'date_resolved': fields.Datetime.now(),
        })
        self._clear_activities()
        self._post_to_document(_(
            "Approval refused by %(user)s: %(reason)s",
            user=self.env.user.name, reason=reason))
        record = self.record_ref()
        reject_method = self.rule_id.reject_method_name
        if record and reject_method:
            getattr(record.sudo().with_context(approval_reject_reason=reason),
                    reject_method)()

    @api.model
    def _cancel_for(self, records, method_name=None):
        """Cancel every live approval of the given documents."""
        if not records:
            return
        domain = [('res_model', '=', records._name),
                  ('res_id', 'in', records.ids),
                  ('state', 'in', ('pending', 'approved', 'error'))]
        if method_name:
            domain.append(('method_name', '=', method_name))
        requests = self.sudo().search(domain)
        requests._clear_activities()
        requests.write({'state': 'cancel',
                        'date_resolved': fields.Datetime.now()})

    # ------------------------------------------------------------------
    # Document / activity plumbing
    # ------------------------------------------------------------------
    def record_ref(self):
        """The approved document as a recordset (may be empty if deleted)."""
        self.ensure_one()
        if self.res_model not in self.env:
            return self.env['approval.request'].browse()
        return self.env[self.res_model].sudo().browse(self.res_id).exists()

    def _post_to_document(self, body):
        self.ensure_one()
        record = self.record_ref()
        if record and hasattr(record, 'message_post'):
            record.message_post(body=body)
        # Approvers only have read access to approval.request, but the audit
        # trail must still be written when they act.
        self.sudo().message_post(body=body)

    def _schedule_current_activity(self):
        self.ensure_one()
        record = self.record_ref()
        if not record or not hasattr(record, 'activity_schedule'):
            return
        self._clear_activities()
        step = self.current_step_id
        for approver in step.approver_ids:
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                note=_("%(document)s — step '%(step)s' needs your approval.",
                       document=self.res_name or record.display_name,
                       step=step.name),
                user_id=approver.id)

    def _clear_activities(self):
        for request in self:
            record = request.record_ref()
            if record and hasattr(record, 'activity_feedback'):
                record.activity_feedback(['mail.mail_activity_data_todo'])

    @api.model
    def _blocked_notification(self, records, result=None):
        """What a gated button returns when approval is still required."""
        if len(records) == 1:
            message = _("%s has been sent for approval.", records.display_name)
        else:
            message = _("%s documents have been sent for approval.",
                        len(records))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _("Approval required"),
                'message': message,
                'next': result if isinstance(result, dict) else {
                    'type': 'ir.actions.act_window_close'},
            },
        }

    # ------------------------------------------------------------------
    # Client API
    # ------------------------------------------------------------------
    @api.model
    def approval_banner_data(self, res_model, res_id):
        """Everything the injected form banner needs, as plain JSON."""
        empty = {'enabled': False}
        if not res_id or res_model not in self.env:
            return empty
        if not self.env['approval.rule'].sudo().search_count(
                [('res_model', '=', res_model)], limit=1):
            return empty
        request = self.search([
            ('res_model', '=', res_model), ('res_id', '=', res_id),
        ], order='id desc', limit=1)
        if not request:
            return empty
        return {
            'enabled': True,
            'id': request.id,
            'name': request.name,
            'state': request.state,
            'rule_name': request.rule_id.name or '',
            'method_name': request.method_name,
            'can_approve': request.can_approve,
            'current_step_id': request.current_step_id.id or False,
            'reject_reason': request.reject_reason or '',
            'steps': [{
                'id': step.id,
                'sequence': step.sequence,
                'name': step.name,
                'status': step.status,
                'mode': step.approval_mode,
                'is_current': step.id == request.current_step_id.id,
                'approver_names': step.approver_names,
                'approved_by': step.approved_user_ids.mapped('name'),
            } for step in request.step_ids.sorted('sequence')],
        }

    @api.model
    def approval_models(self):
        """Models that have at least one active rule (for session_info)."""
        return sorted({
            rule['res_model'] for rule in self.env['approval.rule'].sudo()
            .search_read([], ['res_model'], load=False)
            if rule['res_model']
        })

    @api.model
    def _awaiting_count(self, res_model=None):
        domain = [('state', '=', 'pending'),
                  ('pending_approver_ids', 'in', self.env.uid)]
        if res_model:
            domain.append(('res_model', '=', res_model))
        return self.search_count(domain)

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def approval_action_approve(self):
        """Approve the current step (called from the injected banner)."""
        for request in self:
            if not request.current_step_id:
                raise UserError(_("There is no pending step to approve."))
            request.current_step_id.action_approve_step()
        return True

    def approval_action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Refuse"),
            'res_model': 'approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_step_id': self.current_step_id.id,
            },
        }


class ApprovalStep(models.Model):
    _name = 'approval.step'
    _description = 'Approval Step'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'approval.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='request_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True)
    approval_mode = fields.Selection(
        APPROVAL_MODE_SELECTION, required=True, default='any')
    approver_ids = fields.Many2many(
        'res.users', 'approval_step_candidate_rel', 'step_id', 'user_id',
        string='Approvers')
    approved_user_ids = fields.Many2many(
        'res.users', 'approval_step_done_rel', 'step_id', 'user_id',
        string='Approved By', copy=False)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True, copy=False, index=True)
    reject_reason = fields.Char(copy=False)
    is_current = fields.Boolean(compute='_compute_is_current')
    can_approve = fields.Boolean(compute='_compute_can_approve')
    approver_names = fields.Char(compute='_compute_approver_names')

    @api.depends('request_id.step_ids.status', 'sequence', 'status')
    def _compute_is_current(self):
        for step in self:
            pending = step.request_id.step_ids.filtered(
                lambda s: s.status == 'pending').sorted('sequence')
            step.is_current = bool(pending) and pending[0] == step

    @api.depends_context('uid')
    @api.depends('request_id.step_ids.status', 'sequence', 'status',
                 'approver_ids', 'approved_user_ids')
    def _compute_can_approve(self):
        for step in self:
            step.can_approve = step._user_can_approve()

    @api.depends('approver_ids')
    def _compute_approver_names(self):
        for step in self:
            step.approver_names = ", ".join(
                step.approver_ids.mapped('name')) or _("(no approver resolved)")

    def _user_can_approve(self):
        """Fresh (non-cached) check: may the current user approve this now."""
        self.ensure_one()
        if self.status != 'pending' or self.request_id.state != 'pending':
            return False
        pending = self.request_id.step_ids.filtered(
            lambda s: s.status == 'pending').sorted('sequence')
        if not pending or pending[0].id != self.id:
            return False
        user = self.env.user
        if user in self.approved_user_ids:
            return False
        if user in self.approver_ids:
            return True
        override = self.request_id.override_group_id
        return bool(override) and override in user.all_group_ids

    def _is_satisfied(self):
        self.ensure_one()
        if self.approval_mode == 'all':
            return bool(self.approver_ids) and all(
                user in self.approved_user_ids for user in self.approver_ids)
        return bool(self.approved_user_ids)

    def action_approve_step(self):
        for step in self:
            if not step._user_can_approve():
                raise UserError(_(
                    "You cannot approve this step (not an approver, or not "
                    "the current step)."))
            step.sudo().approved_user_ids = [(4, self.env.user.id)]
            if step._is_satisfied():
                step.sudo().status = 'approved'
            step.request_id._post_to_document(_(
                "%(user)s approved step '%(step)s'.",
                user=self.env.user.name, step=step.name))
            step.request_id.sudo()._recompute_state(resume=True)
        return True

    def action_reject_step(self):
        self.ensure_one()
        return self.request_id.approval_action_reject()

# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import logging
import time
from datetime import timedelta

from nwos import _, api, fields, models
from nwos.exceptions import AccessError, UserError, ValidationError

from ..utils import iso_utc


_logger = logging.getLogger(__name__)


class NextBotApproval(models.Model):
    _name = 'nextbot.approval'
    _description = 'NextBot Tool Approval'
    _order = 'id desc'

    run_id = fields.Many2one('nextbot.run', required=True, ondelete='cascade', index=True)
    conversation_id = fields.Many2one(
        related='run_id.conversation_id', store=True, readonly=True, index=True,
    )
    user_id = fields.Many2one(
        related='run_id.user_id', store=True, readonly=True, index=True,
    )
    tool_name = fields.Char(required=True, index=True)
    arguments = fields.Json(default=dict, required=True)
    summary = fields.Text()
    summary_html = fields.Html(sanitize=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('executing', 'Executing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
        ('superseded', 'Superseded'),
    ], required=True, default='pending', index=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    expires_at = fields.Datetime(required=True, index=True)
    resolved_at = fields.Datetime(index=True)
    resolved_by_id = fields.Many2one('res.users', ondelete='set null')
    result = fields.Json(default=dict)
    preview = fields.Json(default=dict, help='Structured card preview rendered by the workspace.')
    error_message = fields.Text()
    operation_ids = fields.One2many('nextbot.tool.execution', 'approval_id')

    @api.model
    def create_pending(
        self, run, tool_name, arguments, summary='', summary_html='', ttl_minutes=15,
        preview=None,
    ):
        run.ensure_one()
        return self.create({
            'run_id': run.id,
            'tool_name': tool_name,
            'arguments': arguments,
            'summary': summary,
            'summary_html': summary_html,
            'preview': preview or {},
            'expires_at': fields.Datetime.now() + timedelta(minutes=ttl_minutes),
        })

    def _ensure_current_user(self):
        self.ensure_one()
        if self.user_id != self.env.user:
            raise AccessError(_('You cannot decide this NextBot approval.'))
        self.run_id._ensure_current_user()
        return True

    def _serialize(self):
        self.ensure_one()
        return {
            'id': self.id,
            'run_id': self.run_id.id,
            'conversation_id': self.conversation_id.id,
            'tool': self.tool_name,
            'arguments': self.env['nextbot.tool.registry'].redact(self.arguments or {}),
            'summary': self.summary or '',
            'summary_html': self.summary_html or '',
            'preview': self.preview or False,
            'state': self.state,
            'requested_at': iso_utc(self.requested_at),
            'expires_at': iso_utc(self.expires_at),
            'resolved_at': iso_utc(self.resolved_at),
            'resolved_by_id': self.resolved_by_id.id or False,
            'error': self.error_message or False,
            'operations': [operation._serialize() for operation in self.operation_ids],
        }

    def _lock_pending(self):
        """Lock after ownership validation so concurrent decisions execute once."""
        self.ensure_one()
        self._ensure_current_user()
        # Run first, approval second: cancellation uses the same lock order and
        # therefore cannot deadlock with an approval decision.
        self.env.cr.execute(
            'SELECT status FROM nextbot_run WHERE id = %s FOR UPDATE',
            [self.run_id.id],
        )
        run_row = self.env.cr.fetchone()
        if not run_row:
            raise UserError(_('The NextBot run no longer exists.'))
        self.env.cr.execute(
            'SELECT state, expires_at FROM nextbot_approval WHERE id = %s FOR UPDATE',
            [self.id],
        )
        row = self.env.cr.fetchone()
        if not row:
            raise UserError(_('The NextBot approval no longer exists.'))
        state, expires_at = row
        self.invalidate_recordset(['state', 'expires_at'])
        if state != 'pending':
            return False
        if run_row[0] != 'waiting_approval':
            raise ValidationError(_('This run is no longer waiting for approval.'))
        if expires_at and expires_at < fields.Datetime.now():
            self._expire_locked(run_row[0])
            return False
        return True

    def _expire_locked(self, run_status):
        """Persist an expiry while the run and approval rows are locked."""
        self.ensure_one()
        now = fields.Datetime.now()
        self.sudo().write({
            'state': 'expired',
            'resolved_at': now,
            'error_message': False,
        })
        run = self.run_id
        message = _(
            'The requested action expired before it was approved. No ERP data was changed.'
        )
        run._add_event('approval.resolved', {
            'approval_id': self.id,
            'decision': 'expired',
        })
        if run.runtime_version >= 2 and run_status not in (
            'completed', 'partial', 'failed', 'cancelled', 'interrupted'
        ):
            self.operation_ids.filtered(
                lambda operation: operation.state == 'proposed'
            ).sudo().write({'state': 'superseded'})
            run.sudo().write({
                'response_text': message,
                'pause_reason': 'input',
                'status': 'waiting_input',
            })
            run._assistant_events(message)
            run._post_assistant_message(message)
            run._add_event('run.status', {
                'status': 'waiting_input',
                'message': _('Approval expired; the task can be adjusted and resumed.'),
            })
        elif run_status not in ('completed', 'failed', 'cancelled'):
            run.sudo().write({
                'response_text': message,
                'error_message': message,
            })
            run._assistant_events(message)
            run._add_event('run.error', {'message': message})
            run._post_assistant_if_status(message, run_status)
            run._set_status('failed', _('Approval expired.'))
        return True

    def _expire_if_due(self):
        """Atomically expire one pending approval in its initiating user context."""
        self.ensure_one()
        self._ensure_current_user()
        self.env.cr.execute(
            'SELECT status FROM nextbot_run WHERE id = %s FOR UPDATE',
            [self.run_id.id],
        )
        run_row = self.env.cr.fetchone()
        if not run_row:
            return False
        self.env.cr.execute(
            'SELECT state, expires_at FROM nextbot_approval WHERE id = %s FOR UPDATE',
            [self.id],
        )
        row = self.env.cr.fetchone()
        if not row:
            return False
        state, expires_at = row
        self.invalidate_recordset(['state', 'expires_at'])
        if state != 'pending' or not expires_at or expires_at >= fields.Datetime.now():
            return False
        return self._expire_locked(run_row[0])

    @api.model
    def _cron_expire_pending(self, batch_size=100):
        """Expire unattended approvals using their original user/company scope."""
        batch_size = min(max(int(batch_size or 100), 1), 500)
        candidates = self.sudo().search([
            ('state', '=', 'pending'),
            ('expires_at', '<', fields.Datetime.now()),
        ], order='expires_at, id', limit=batch_size)
        processed = 0
        for candidate in candidates:
            run = candidate.run_id
            user = run.user_id
            allowed_companies = run.allowed_company_ids & user.company_ids
            company = (
                run.company_id
                if run.company_id in allowed_companies
                else allowed_companies[:1]
            )
            if not user or not company or not allowed_companies:
                _logger.warning(
                    'Cannot expire NextBot approval %s: its run user/company context is unavailable.',
                    candidate.id,
                )
                continue
            approval = candidate.with_user(user).with_context(
                allowed_company_ids=allowed_companies.ids,
            ).with_company(company)
            if approval._expire_if_due():
                processed += 1
                if self.env.context.get('cron_id'):
                    self.env['ir.cron']._commit_progress(1)
        remaining = self.sudo().search_count([
            ('state', '=', 'pending'),
            ('expires_at', '<', fields.Datetime.now()),
        ])
        if remaining and self.env.context.get('cron_id'):
            self.env['ir.cron']._commit_progress(0, remaining=remaining)
        return processed

    def action_approve(self):
        self.ensure_one()
        if not self._lock_pending():
            return self._serialize()
        if self.run_id.runtime_version >= 2 and self.operation_ids:
            return self._action_approve_batch_locked()
        self.sudo().write({
            'state': 'executing',
            'resolved_by_id': self.env.user.id,
        })
        run_user = self.run_id.user_id
        allowed_companies = self.run_id.allowed_company_ids & run_user.company_ids
        company = self.run_id.company_id
        if not allowed_companies or company not in allowed_companies:
            self.sudo().write({
                'state': 'failed',
                'resolved_at': fields.Datetime.now(),
                'error_message': _('The original run company is no longer allowed.'),
            })
            self.run_id._fail_run(_('The original run company is no longer allowed.'))
            return self._serialize()
        run = self.run_id.with_user(run_user).with_context(
            allowed_company_ids=allowed_companies.ids,
        ).with_company(company)
        run._add_event('approval.resolved', {
            'approval_id': self.id,
            'decision': 'approved',
        })
        run._add_event('tool.started', {
            'tool': self.tool_name,
            'approval_id': self.id,
        })
        try:
            result = run.env['nextbot.tool.registry'].execute(
                self.tool_name,
                self.arguments or {},
                run,
            )
            self.sudo().write({
                'state': 'approved',
                'resolved_at': fields.Datetime.now(),
                'result': result,
                'error_message': False,
            })
            safe_result = run.env['nextbot.tool.registry'].redact(result)
            completed_payload = {
                'tool': self.tool_name,
                'approval_id': self.id,
                'result': safe_result,
            }
            if isinstance(result, dict) and isinstance(result.get('card'), dict):
                completed_payload['card'] = result['card']
            run._add_event('tool.completed', completed_payload)
            response_text = (
                result.get('text') if isinstance(result, dict) else str(result or '')
            ) or _('The approved action completed.')
            response_html = result.get('html') if isinstance(result, dict) else False
            run.sudo().response_text = response_text
            run._assistant_events(response_text)
            run._post_assistant_message(response_html or response_text, html=bool(response_html))
            run._set_status('completed', _('Approved action completed.'))
        except (AccessError, UserError, ValidationError, ValueError, TypeError) as error:
            _logger.warning('NextBot approval %s execution failed: %s', self.id, error)
            self.sudo().write({
                'state': 'failed',
                'resolved_at': fields.Datetime.now(),
                'error_message': str(error)[:2000],
            })
            run._add_event('tool.failed', {
                'tool': self.tool_name,
                'approval_id': self.id,
                'message': str(error)[:2000],
            })
            run._fail_run(str(error))
        return self._serialize()

    def _action_approve_batch_locked(self):
        """Execute a v2 approval batch once, then resume the same task."""
        self.ensure_one()
        self.sudo().write({
            'state': 'executing',
            'resolved_by_id': self.env.user.id,
        })
        run_user = self.run_id.user_id
        companies = self.run_id.allowed_company_ids & run_user.company_ids
        company = self.run_id.company_id
        if not companies or company not in companies:
            raise ValidationError(_('The original task company is no longer allowed.'))
        run = self.run_id.with_user(run_user).with_context(
            allowed_company_ids=companies.ids,
        ).with_company(company)
        Registry = run.env['nextbot.tool.registry']
        run._add_event('approval.resolved', {
            'approval_id': self.id,
            'decision': 'approved',
        })
        failed = False
        for operation_sudo in self.operation_ids.sorted('id'):
            if operation_sudo.state == 'completed':
                continue
            if operation_sudo.state != 'proposed':
                failed = _('Operation %s is no longer executable.', operation_sudo.id)
                break
            operation = operation_sudo.with_env(run.env)
            started = time.monotonic()
            try:
                # Validate and prepare again at approval time so permissions,
                # company scope, record state, and normalized values are fresh.
                Registry.validate_arguments(operation.tool_name, operation.arguments)
                prepared = Registry.prepare_write(operation.tool_name, operation.arguments, run)
                operation.sudo().write({
                    'state': 'running',
                    'arguments': prepared['arguments'],
                    'attempt_count': operation.attempt_count + 1,
                    'started_at': fields.Datetime.now(),
                })
                run._add_event('tool.started', {
                    'tool': operation.tool_name,
                    'execution_id': operation.id,
                    'approval_id': self.id,
                })
                result = Registry.execute(operation.tool_name, prepared['arguments'], run)
                operation.sudo().write({
                    'state': 'completed',
                    'result': result,
                    'error_message': False,
                    'completed_at': fields.Datetime.now(),
                    'duration_ms': int((time.monotonic() - started) * 1000),
                })
                run._add_event('tool.completed', {
                    'tool': operation.tool_name,
                    'execution_id': operation.id,
                    'approval_id': self.id,
                    'result': Registry.redact(result),
                    'duration_ms': operation.duration_ms,
                })
            except (AccessError, UserError, ValidationError, ValueError, KeyError, TypeError) as error:
                failed = str(error)[:2000]
                operation.sudo().write({
                    'state': 'failed',
                    'error_message': failed,
                    'completed_at': fields.Datetime.now(),
                    'duration_ms': int((time.monotonic() - started) * 1000),
                })
                run._add_event('tool.failed', {
                    'tool': operation.tool_name,
                    'execution_id': operation.id,
                    'approval_id': self.id,
                    'message': failed,
                })
                break
        if failed:
            self.sudo().write({
                'state': 'failed',
                'resolved_at': fields.Datetime.now(),
                'error_message': failed,
            })
            message = _(
                'The approved batch stopped safely after an operation failed: %s. '
                'Completed operations were saved and will not be repeated. Send a correction to resume.',
                failed,
            )
            run.sudo().write({
                'response_text': message,
                'pause_reason': 'input',
                'status': 'waiting_input',
            })
            run._assistant_events(message)
            run._post_assistant_message(message)
            run._add_event('run.status', {'status': 'waiting_input', 'message': _('Batch needs repair.')})
            return self._serialize()

        self.sudo().write({
            'state': 'approved',
            'resolved_at': fields.Datetime.now(),
            'error_message': False,
            'result': {'completed_execution_ids': self.operation_ids.ids},
        })
        write_steps = run.step_ids.filtered(
            lambda step: step.plan_revision == run.plan_revision
            and step.step_type == 'write'
            and step.status not in ('completed', 'skipped')
        )
        if write_steps:
            write_steps.sudo().write({
                'status': 'completed',
                'completed_at': fields.Datetime.now(),
            })
            for step in write_steps:
                step._emit_status(_('Approved changes completed.'))
        verification_steps = run.step_ids.filtered(
            lambda step: step.plan_revision == run.plan_revision
            and step.step_type == 'verification'
            and step.status in ('pending', 'queued', 'running')
        )
        if not verification_steps:
            verification_steps = run.env['nextbot.run.step'].sudo().create({
                'run_id': run.id,
                'key': 'r%s_verify_approval_%s' % (run.plan_revision, self.id),
                'plan_revision': run.plan_revision,
                'sequence': max(run.step_ids.mapped('sequence') or [0]) + 10,
                'title': _('Verify approved changes'),
                'objective': _(
                    'Read back every record affected by approval batch %s and confirm the requested values were stored.',
                    self.id,
                ),
                'step_type': 'verification',
                'parallel_safe': True,
                'dependency_ids': [(6, 0, write_steps.ids)],
            })
            run._add_event('task.plan.revised', {'task': run._serialize()['task']})
        run.sudo().write({
            # Verification workers may start as soon as this request commits.
            # Put the run directly in their claimable state instead of also
            # launching the coordinator and racing both workers on events.
            'status': 'verifying',
            'pause_reason': False,
            'response_text': _('Approved changes completed; verification is continuing.'),
        })
        run._schedule_ready_steps()
        current_steps = run.step_ids.filtered(
            lambda step: step.plan_revision == run.plan_revision
            and step.status in ('queued', 'running')
        )
        if not current_steps:
            run._trigger_coordinator()
        return self._serialize()

    def action_reject(self):
        self.ensure_one()
        if not self._lock_pending():
            return self._serialize()
        self.sudo().write({
            'state': 'rejected',
            'resolved_at': fields.Datetime.now(),
            'resolved_by_id': self.env.user.id,
        })
        run = self.run_id
        if run.runtime_version >= 2:
            self.operation_ids.filtered(
                lambda operation: operation.state == 'proposed'
            ).sudo().write({'state': 'superseded'})
            message = _(
                'The proposed changes were rejected and nothing new was executed. '
                'Send a correction or a different instruction to continue this task.'
            )
            run._add_event('approval.resolved', {
                'approval_id': self.id,
                'decision': 'rejected',
            })
            run.sudo().write({
                'response_text': message,
                'pause_reason': 'input',
                'status': 'waiting_input',
            })
            run._assistant_events(message)
            run._post_assistant_message(message)
            run._add_event('run.status', {'status': 'waiting_input', 'message': _('Proposal rejected.')})
            return self._serialize()
        message = _('The requested action was rejected. No ERP data was changed.')
        run._add_event('approval.resolved', {
            'approval_id': self.id,
            'decision': 'rejected',
        })
        run.sudo().response_text = message
        run._assistant_events(message)
        run._post_assistant_message(message)
        run._set_status('completed', _('Action rejected.'))
        return self._serialize()

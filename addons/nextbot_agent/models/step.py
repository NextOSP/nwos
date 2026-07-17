# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import json
import logging
import time
import uuid
from datetime import timedelta

from nwos import _, api, fields, models
from nwos.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)


class NextBotRunStep(models.Model):
    _name = 'nextbot.run.step'
    _description = 'NextBot Durable Plan Step'
    _order = 'run_id, sequence, id'

    run_id = fields.Many2one('nextbot.run', required=True, ondelete='cascade', index=True)
    conversation_id = fields.Many2one(
        related='run_id.conversation_id', store=True, readonly=True, index=True,
    )
    user_id = fields.Many2one(related='run_id.user_id', store=True, readonly=True, index=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True, readonly=True, index=True)
    key = fields.Char(required=True, index=True)
    plan_revision = fields.Integer(default=1, required=True, index=True)
    sequence = fields.Integer(required=True, default=10)
    title = fields.Char(required=True)
    objective = fields.Text(required=True)
    step_type = fields.Selection([
        ('read', 'Read / Research'),
        ('write', 'Write'),
        ('verification', 'Verification'),
    ], required=True, default='read', index=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled'),
    ], required=True, default='pending', index=True)
    dependency_ids = fields.Many2many(
        'nextbot.run.step', 'nextbot_step_dependency_rel',
        'step_id', 'dependency_id', string='Dependencies',
    )
    input_data = fields.Json(default=dict)
    output_data = fields.Json(default=dict)
    error_message = fields.Text()
    attempt_count = fields.Integer(default=0, copy=False)
    max_attempts = fields.Integer(default=3)
    parallel_safe = fields.Boolean(default=True)
    lease_token = fields.Char(copy=False, index=True)
    lease_expires_at = fields.Datetime(copy=False, index=True)
    heartbeat_at = fields.Datetime(copy=False, index=True)
    started_at = fields.Datetime(copy=False)
    completed_at = fields.Datetime(copy=False)
    duration_ms = fields.Integer(copy=False)

    _run_key_unique = models.Constraint(
        'UNIQUE(run_id, key)', 'Plan-step keys must be unique inside a NextBot run.',
    )

    def _ensure_current_user(self):
        for step in self:
            step.run_id._ensure_current_user()
        return True

    def _serialize(self):
        self.ensure_one()
        return {
            'id': self.id,
            'key': self.key,
            'plan_revision': self.plan_revision,
            'sequence': self.sequence,
            'title': self.title,
            'objective': self.objective,
            'type': self.step_type,
            'status': self.status,
            'dependencies': self.dependency_ids.mapped('key'),
            'attempt_count': self.attempt_count,
            'max_attempts': self.max_attempts,
            'parallel_safe': self.parallel_safe,
            'output': self.output_data or False,
            'error': self.error_message or False,
        }

    def _emit_status(self, message=None):
        self.ensure_one()
        payload = {'step': self._serialize()}
        if message:
            payload['message'] = message
        return self.run_id._add_event('task.step.status', payload)

    @api.model
    def _claim_ready(self):
        lease_token = str(uuid.uuid4())
        self.env.cr.execute(
            """
            WITH candidate AS (
                SELECT step.id
                  FROM nextbot_run_step step
                  JOIN nextbot_run run ON run.id = step.run_id
                 WHERE step.status = 'queued'
                   AND step.step_type IN ('read', 'verification')
                   AND run.status IN ('running', 'verifying')
                   AND NOT EXISTS (
                       SELECT 1
                         FROM nextbot_run_step active
                        WHERE active.run_id = step.run_id
                          AND active.status = 'running'
                   )
              ORDER BY run.id, step.sequence, step.id
                 LIMIT 1
            FOR UPDATE OF run, step SKIP LOCKED
            )
            UPDATE nextbot_run_step AS step
               SET status = 'running',
                   attempt_count = step.attempt_count + 1,
                   started_at = COALESCE(step.started_at, NOW() AT TIME ZONE 'UTC'),
                   heartbeat_at = NOW() AT TIME ZONE 'UTC',
                   lease_token = %s,
                   lease_expires_at = NOW() AT TIME ZONE 'UTC' + INTERVAL '5 minutes'
              FROM candidate
             WHERE step.id = candidate.id
         RETURNING step.id
            """,
            [lease_token],
        )
        row = self.env.cr.fetchone()
        if not row:
            return self.browse()
        self.env.cr.commit()
        return self.browse(row[0])

    def _execute_read_step(self):
        self.ensure_one()
        run = self.run_id
        if run.cancel_requested or run.status == 'cancelled':
            self.sudo().write({'status': 'cancelled', 'completed_at': fields.Datetime.now()})
            self._emit_status(_('Step cancelled.'))
            return self

        started = time.monotonic()
        self._emit_status(_('Working on %s.', self.title))
        Registry = self.env['nextbot.tool.registry']
        LLM = self.env['nextbot.llm']
        settings = LLM.settings()
        error = LLM.configuration_error(settings)
        if error:
            raise UserError(error)
        definitions = Registry.get_definitions(access='read')
        state = run._task_state_context(include_outputs=True)
        messages = [
            {'role': 'system', 'content': run._agent_system_prompt() + (
                '\n\nYou are executing one read-only plan step. Use only the supplied '
                'read tools. Return a concise evidence summary. Never request an ERP write.'
            )},
            {'role': 'user', 'content': (
                'Task goal: %s\nStep: %s\nObjective: %s\n\nCurrent task state:\n%s'
            ) % (run.goal or run.prompt, self.title, self.objective, state)},
        ]
        max_calls = run._config_int('nextbot_agent.max_step_tool_calls', 12, 1, 50)
        calls = 0
        turns = 0
        try:
            while True:
                if run._budget_reached():
                    raise UserError(_('The task work budget was reached during this read step.'))
                turns += 1
                if turns > max_calls + 6:
                    raise UserError(_('The read step exceeded its model-loop budget.'))
                now = fields.Datetime.now()
                self.sudo().write({
                    'heartbeat_at': now,
                    'lease_expires_at': now + timedelta(minutes=5),
                })
                run._touch_lease()
                run._increment_counter('model_call_count')
                response = LLM.complete(settings, messages, tools=definitions or None)
                tool_calls = response.get('tool_calls') or []
                if not tool_calls:
                    content = LLM.plain_content(response.get('content') or '').strip()
                    if not content:
                        content = _('No relevant evidence was found for this step.')
                    self.sudo().write({
                        'status': 'completed',
                        'output_data': {'summary': content},
                        'error_message': False,
                        'completed_at': fields.Datetime.now(),
                        'duration_ms': int((time.monotonic() - started) * 1000),
                        'lease_token': False,
                        'lease_expires_at': False,
                    })
                    self._emit_status(_('Step completed.'))
                    break
                messages.append(response)
                tool_messages = []
                for tool_call in tool_calls:
                    if calls >= max_calls:
                        tool_messages.append({
                            'role': 'tool',
                            'tool_call_id': tool_call.get('id') or 'budget',
                            'content': json.dumps({'error': 'Step tool budget reached. Summarize available evidence.'}),
                        })
                        continue
                    name, arguments = LLM.parse_tool_call(tool_call)
                    provider = Registry._get_provider(name)
                    if Registry.effective_access(name, provider) != 'read':
                        result = {'error': 'Writes are not permitted in a read step.'}
                    else:
                        result = run._execute_tool_call(
                            name, arguments, step=self, allow_write=False,
                        )
                    calls += 1
                    tool_messages.append({
                        'role': 'tool',
                        'tool_call_id': tool_call.get('id') or name,
                        'content': json.dumps(result, ensure_ascii=False, default=str),
                    })
                messages.extend(tool_messages)
        except (AccessError, UserError, ValidationError, ValueError, KeyError, TypeError) as exc:
            _logger.warning('NextBot step %s failed: %s', self.id, exc)
            self._handle_failure(str(exc), started)
        except Exception:  # noqa: BLE001
            _logger.exception('Unexpected NextBot step failure for %s', self.id)
            self._handle_failure(_('Unexpected read-step failure.'), started)
        run._schedule_ready_steps()
        run._trigger_coordinator()
        return self

    def _handle_failure(self, message, started):
        retry = self.attempt_count < self.max_attempts
        self.sudo().write({
            'status': 'queued' if retry else 'failed',
            'error_message': str(message)[:2000],
            'duration_ms': int((time.monotonic() - started) * 1000),
            'completed_at': False if retry else fields.Datetime.now(),
            'lease_token': False,
            'lease_expires_at': False,
        })
        self._emit_status(_('Step will retry.') if retry else _('Step failed.'))

    @api.model
    def _cron_process_ready_steps(self, batch_size=1):
        processed = 0
        for _index in range(min(max(int(batch_size or 1), 1), 5)):
            step_sudo = self.sudo()._claim_ready()
            if not step_sudo:
                break
            run = step_sudo.run_id
            user = run.user_id
            companies = run.allowed_company_ids & user.company_ids
            company = run.company_id if run.company_id in companies else companies[:1]
            if not user.active or not company:
                step_sudo._handle_failure(_('The task user or company is unavailable.'), time.monotonic())
                continue
            step = step_sudo.with_user(user).with_context(
                allowed_company_ids=companies.ids,
                nextbot_agent_async_worker=True,
            ).with_company(company)
            step._execute_read_step()
            processed += 1
            if self.env.context.get('cron_id'):
                self.env['ir.cron']._commit_progress(1)
        remaining = self.sudo().search_count([('status', '=', 'queued')])
        if remaining and self.env.context.get('cron_id'):
            self.env['ir.cron']._commit_progress(0, remaining=remaining)
        return processed

    @api.model
    def _cron_recover_expired_leases(self):
        stale = self.sudo().search([
            ('status', '=', 'running'),
            ('lease_expires_at', '<', fields.Datetime.now()),
        ], limit=100)
        for step in stale:
            retry = step.attempt_count < step.max_attempts
            step.write({
                'status': 'queued' if retry else 'failed',
                'error_message': _('The worker lease expired; the step was recovered.'),
                'lease_token': False,
                'lease_expires_at': False,
            })
            step._emit_status(_('Recovered an interrupted step.'))
            step.run_id._trigger_coordinator()
        return len(stale)

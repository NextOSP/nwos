# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import hashlib
import json

from nwos import api, fields, models


class NextBotToolExecution(models.Model):
    _name = 'nextbot.tool.execution'
    _description = 'NextBot Durable Tool Execution'
    _order = 'id'

    run_id = fields.Many2one('nextbot.run', required=True, ondelete='cascade', index=True)
    step_id = fields.Many2one('nextbot.run.step', ondelete='set null', index=True)
    approval_id = fields.Many2one('nextbot.approval', ondelete='set null', index=True)
    conversation_id = fields.Many2one(
        related='run_id.conversation_id', store=True, readonly=True, index=True,
    )
    user_id = fields.Many2one(related='run_id.user_id', store=True, readonly=True, index=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True, readonly=True, index=True)
    tool_name = fields.Char(required=True, index=True)
    arguments = fields.Json(default=dict, required=True)
    result = fields.Json(default=dict)
    access = fields.Selection([('read', 'Read'), ('write', 'Write')], required=True, index=True)
    state = fields.Selection([
        ('proposed', 'Proposed'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('outcome_unknown', 'Outcome Unknown'),
        ('cancelled', 'Cancelled'),
        ('superseded', 'Superseded'),
    ], required=True, default='running', index=True)
    idempotency_key = fields.Char(required=True, index=True)
    attempt_count = fields.Integer(default=0)
    max_attempts = fields.Integer(default=3)
    error_message = fields.Text()
    started_at = fields.Datetime()
    completed_at = fields.Datetime()
    duration_ms = fields.Integer()

    _run_idempotency_unique = models.Constraint(
        'UNIQUE(run_id, idempotency_key)',
        'A NextBot tool operation can only be recorded once per run.',
    )

    @api.model
    def make_key(self, run, tool_name, arguments, suffix=''):
        canonical = json.dumps(arguments or {}, ensure_ascii=False, sort_keys=True, default=str)
        raw = '%s\0%s\0%s\0%s' % (run.id, tool_name, canonical, suffix or '')
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _serialize(self):
        self.ensure_one()
        Registry = self.env['nextbot.tool.registry']
        return {
            'id': self.id,
            'step_id': self.step_id.id or False,
            'tool': self.tool_name,
            'arguments': Registry.redact(self.arguments or {}),
            'result': Registry.redact(self.result or {}) if self.state == 'completed' else False,
            'access': self.access,
            'state': self.state,
            'attempt_count': self.attempt_count,
            'error': self.error_message or False,
            'duration_ms': self.duration_ms or 0,
        }


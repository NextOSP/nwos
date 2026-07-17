# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models

from ..utils import iso_utc


class NextBotRunEvent(models.Model):
    _name = 'nextbot.run.event'
    _description = 'NextBot Run Event'
    _order = 'run_id, sequence, id'

    run_id = fields.Many2one('nextbot.run', required=True, ondelete='cascade', index=True)
    conversation_id = fields.Many2one(
        related='run_id.conversation_id', store=True, readonly=True, index=True,
    )
    user_id = fields.Many2one(
        related='run_id.user_id', store=True, readonly=True, index=True,
    )
    sequence = fields.Integer(required=True, index=True)
    event_type = fields.Char(required=True, index=True)
    payload = fields.Json(default=dict)
    created_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)

    _run_sequence_unique = models.Constraint(
        'UNIQUE(run_id, sequence)',
        'Run event sequence numbers must be unique.',
    )

    def _serialize(self):
        self.ensure_one()
        return {
            'id': self.id,
            'run_id': self.run_id.id,
            'sequence': self.sequence,
            'type': self.event_type,
            'timestamp': iso_utc(self.created_at),
            'payload': self.payload or {},
        }
